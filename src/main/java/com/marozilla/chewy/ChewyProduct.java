package com.marozilla.chewy;

import org.apache.poi.ss.usermodel.Row;

public class ChewyProduct {
	String SEPARATOR = "|";
	String productType = "";
	String url = "";
	String brandName = "";
	String itemName = "";
	String sku = "";
	String imageUrl = "";
	String price = "";
	String option = "";
	String size = "";
	String count = "";
	String pricePerEach = "";

	public static void writeHeaders(Row headers) {
		headers.createCell(0).setCellValue("URL");
		headers.createCell(1).setCellValue("Brand Name");
		headers.createCell(2).setCellValue("Item Name");
		headers.createCell(3).setCellValue("SKU");
		headers.createCell(4).setCellValue("Image Url");
		headers.createCell(5).setCellValue("Price");
		headers.createCell(6).setCellValue("Option");
		headers.createCell(7).setCellValue("Size");
		headers.createCell(8).setCellValue("Count");
		headers.createCell(9).setCellValue("Cost Each");
	}

	public void writeRow(Row row) {
		row.createCell(0).setCellValue(url);
		row.createCell(1).setCellValue(brandName);
		row.createCell(2).setCellValue(itemName);
		row.createCell(3).setCellValue(sku);
		row.createCell(4).setCellValue(imageUrl);
		row.createCell(5).setCellValue(price);
		row.createCell(6).setCellValue(option);
		row.createCell(7).setCellValue(size);
		row.createCell(8).setCellValue(count);
		row.createCell(9).setCellValue(pricePerEach);
	}

	@Override
	public String toString() {
		return productType + SEPARATOR + url + SEPARATOR + brandName + SEPARATOR + itemName + SEPARATOR + sku
				+ SEPARATOR + imageUrl + SEPARATOR + price + SEPARATOR + option + SEPARATOR + size + SEPARATOR + count
				+ SEPARATOR + pricePerEach;
	}
}
