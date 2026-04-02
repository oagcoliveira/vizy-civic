from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import auth, politicians, bills, votes, donations, feed, search

app = FastAPI(
    title="Vizy API",
    description="REST API for the Vizy civic data platform",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/auth", tags=["auth"])
app.include_router(politicians.router, prefix="/politicians", tags=["politicians"])
app.include_router(bills.router, prefix="/bills", tags=["bills"])
app.include_router(votes.router, prefix="/votes", tags=["votes"])
app.include_router(donations.router, prefix="/donations", tags=["donations"])
app.include_router(feed.router, prefix="/feed", tags=["feed"])
app.include_router(search.router, prefix="/search", tags=["search"])


@app.get("/health")
def health():
    return {"status": "ok"}
