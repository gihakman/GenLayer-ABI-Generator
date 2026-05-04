from genlayer.py.types import Address, u256
import genlayer.py._native as gl

class WagerContract(gl.Contract):
    """A peer-to-peer subjective betting contract."""

    @gl.public.write
    def create_wager(
        self,
        opponent: Address,
        description: str,
        arbiter: str,
        amount: u256,
    ) -> u256:
        """Create a new wager between creator and opponent."""
        wager_id = 1
        return wager_id

    @gl.public.write
    def accept_wager(self, wager_id: u256) -> bool:
        """Accept an existing wager."""
        return True

    @gl.public.view
    def get_wager(self, wager_id: u256) -> dict:
        """Retrieve wager details."""
        return {
            "wager_id": wager_id,
            "description": "test",
            "status": "open",
        }

    @gl.public.write.payable
    def resolve_wager(self, wager_id: u256) -> dict:
        """Resolve a wager with payment."""
        return {"status": "resolved"}
