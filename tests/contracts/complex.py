from genlayer.py.types import Address, u256, DynArray, TreeMap
import genlayer.py._native as gl

class AuctionContract(gl.Contract):
    """A complex auction contract with optional params and advanced types."""

    @gl.public.write
    def create_auction(
        self,
        item_id: u256,
        title: str,
        reserve_price: u256 = 0,
        duration_days: int = 7,
    ) -> u256:
        """Create an auction with optional reserve price and duration."""
        return 1

    @gl.public.view
    def get_bids(self, auction_id: u256) -> DynArray[dict]:
        """Get all bids as a dynamic array of dicts."""
        return []

    @gl.public.view
    def get_leaderboard(self) -> TreeMap[u256, str]:
        """Return a sorted map of scores to names."""
        return {}

    @gl.public.write.payable
    def place_bid(self, auction_id: u256, amount: u256) -> bool:
        """Place a bid on an auction."""
        return True
