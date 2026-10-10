"""AWS Lambda entry point. Mangum translates Lambda Function URL requests into normal FastAPI requests.

Startup (database setup and, in demo mode, seeding the demo account) runs once when Lambda loads this
module, not on every request; Mangum's per-request lifespan is turned off so data persists between calls.
"""
from mangum import Mangum

from app.main import app, startup

startup()
handler = Mangum(app, lifespan="off")
