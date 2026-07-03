from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from sqlmodel import Session, select
from app.services.db_session import get_session
from app.models import Account, Transaction

router = APIRouter()


class TransferRequest(BaseModel):
    sender_id: str
    receiver_id: str
    amount: int


@router.get("/balance/{account_id}")
def get_balance(account_id: str, session: Session = Depends(get_session)):
    """Returns current score/points balance of an account."""
    account = session.get(Account, account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    return {"account_id": account_id, "score": account.score or 0}


@router.post("/transfer")
def transfer_points(request: TransferRequest, session: Session = Depends(get_session)):
    """Transfer points from one account to another."""
    if request.amount <= 0:
        raise HTTPException(status_code=400, detail="Amount must be positive")

    sender = session.get(Account, request.sender_id)
    receiver = session.get(Account, request.receiver_id)

    if not sender:
        raise HTTPException(status_code=404, detail="Sender account not found")
    if not receiver:
        raise HTTPException(status_code=404, detail="Receiver account not found")
    if (sender.score or 0) < request.amount:
        raise HTTPException(status_code=400, detail="Insufficient balance")

    sender.score = (sender.score or 0) - request.amount
    receiver.score = (receiver.score or 0) + request.amount
    session.add(sender)
    session.add(receiver)

    tx = Transaction(
        sender_id=request.sender_id,
        receiver_id=request.receiver_id,
        amount=request.amount,
    )
    session.add(tx)
    session.commit()

    return {
        "status": "success",
        "transaction_id": tx.id,
        "sender_balance": sender.score,
        "receiver_balance": receiver.score,
    }


@router.get("/history/{account_id}")
def get_transaction_history(account_id: str, session: Session = Depends(get_session)):
    """Returns all transactions involving an account."""
    account = session.get(Account, account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")

    txs = session.exec(
        select(Transaction).where(
            (Transaction.sender_id == account_id) |
            (Transaction.receiver_id == account_id)
        ).order_by(Transaction.timestamp.desc())
    ).all()

    return {"account_id": account_id, "transactions": txs}
