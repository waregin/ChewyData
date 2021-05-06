package com.marozilla.chewy;

public class ChewyProduct {
	String SEPARATOR = "|";
	String URL = "";
	String brandName = "";
	String itemName = "";
	String sku = "";
	String imageUrl = "";
	String price = "";
	String option = "";
	String size = "";
	String count = "";
	String pricePerEach = "";

	@Override
	public String toString() {
		return URL + SEPARATOR + brandName + SEPARATOR + itemName + SEPARATOR + sku
				+ SEPARATOR + imageUrl + SEPARATOR + price + SEPARATOR + option + SEPARATOR + size + SEPARATOR + count
				+ SEPARATOR + pricePerEach;
	}
}
