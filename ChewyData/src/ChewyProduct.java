
public class ChewyProduct {
	String SEPARATOR = "|";
	String URL = null;
	String brandName = null;
	String itemName = null;
	String sku = null;
	String imageUrl = null;
	String price = null;
	String option = null;
	String size = null;
	String count = null;

	@Override
	public String toString() {
		return URL + SEPARATOR + brandName + SEPARATOR + itemName + SEPARATOR + sku
				+ SEPARATOR + imageUrl + SEPARATOR + price + SEPARATOR + option + SEPARATOR + size + SEPARATOR + count;
	}
}
