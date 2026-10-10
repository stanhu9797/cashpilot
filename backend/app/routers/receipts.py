from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import Response
from sqlalchemy.orm import Session

from ..ai.client import AIUnavailable
from ..auth import current_user
from ..config import get_settings
from ..database import get_db
from ..models import Receipt, User
from ..services.categorizer import categorize_many
from ..services.receipts import ALLOWED_TYPES, extract_receipt, sniff_type
from .. import ratelimit
from ..services.storage import read_file, save_file

router = APIRouter(prefix="/api/receipts", tags=["receipts"])


@router.post("")
async def upload_receipt(file: UploadFile = File(...), user: User = Depends(current_user), db: Session = Depends(get_db)):
    settings = get_settings()
    content_type = (file.content_type or "").lower()
    if content_type not in ALLOWED_TYPES:
        raise HTTPException(400, "Upload a photo (JPG, PNG, WEBP) or a PDF.")
    data = await file.read()
    if not data:
        raise HTTPException(400, "The file is empty.")
    if len(data) > settings.max_upload_mb * 1024 * 1024:
        raise HTTPException(413, f"File is larger than {settings.max_upload_mb} MB. Try a smaller photo.")
    real_type = sniff_type(data)
    if real_type is None:
        raise HTTPException(400, "That file isn't a real image or PDF. Choose a photo or PDF of the receipt.")
    content_type = real_type  # trust the bytes, not the label
    ratelimit.check(f"receipt:{user.id}", 30, 3600, "Too many receipts in the last hour.")

    key = save_file(user.id, file.filename or "receipt", data, content_type)
    receipt = Receipt(user_id=user.id, file_key=key, filename=file.filename or "receipt", content_type=content_type)
    db.add(receipt)
    db.commit()

    try:
        extracted = extract_receipt(data, content_type, db=db, user_id=user.id)
    except AIUnavailable as e:
        receipt.status, receipt.error = "failed", str(e)
        db.commit()
        raise HTTPException(503, str(e))

    if not extracted.is_receipt:
        receipt.status, receipt.error = "failed", "Not a receipt"
        db.commit()
        raise HTTPException(422, "That doesn't look like a receipt or invoice. Try another photo.")

    suggestion = None
    if extracted.merchant and extracted.total:
        s = categorize_many(db, user.id, [{"merchant": extracted.merchant, "description": "", "amount": -abs(extracted.total)}])[0]
        suggestion = {"category": s.category, "confidence": s.confidence, "source": s.source, "reason": s.reason}

    receipt.status = "extracted"
    receipt.extracted = extracted.model_dump(mode="json")
    db.commit()
    return {
        "receipt_id": receipt.id,
        "extracted": receipt.extracted,
        "category_suggestion": suggestion,
        "review_threshold": settings.review_threshold,
    }


@router.get("/{receipt_id}/file")
def receipt_file(receipt_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    r = db.get(Receipt, receipt_id)
    if not r or r.user_id != user.id:
        raise HTTPException(404, "Receipt not found.")
    return Response(read_file(r.file_key), media_type=r.content_type)
