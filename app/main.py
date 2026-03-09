from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.cors import CORSMiddleware as StarletteCORSMiddleware

from .routers import auth, categories, statements, stats, transactions, purchase


app = FastAPI(title="Finview - Analizador de gastos")

app.add_middleware(
    StarletteCORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health_check():
    return {"status": "ok"}


app.include_router(auth.router)
app.include_router(categories.router)
app.include_router(statements.router)
app.include_router(stats.router)
app.include_router(transactions.router)
app.include_router(purchase.router)

