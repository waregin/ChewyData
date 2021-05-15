package com.marozilla.chewy;

import org.apache.poi.ss.usermodel.Cell;
import org.apache.poi.ss.usermodel.CellStyle;
import org.apache.poi.ss.usermodel.Font;
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
		CellStyle headerStyle = headers.getSheet().getWorkbook().createCellStyle();
		Font font = headers.getSheet().getWorkbook().createFont();
		font.setBold(true);
		headerStyle.setFont(font);

		makeBoldCell(headers.createCell(0), headerStyle, "URL");
		makeBoldCell(headers.createCell(1), headerStyle, "Brand Name");
		makeBoldCell(headers.createCell(2), headerStyle, "Item Name");
		makeBoldCell(headers.createCell(3), headerStyle, "SKU");
		makeBoldCell(headers.createCell(4), headerStyle, "Image Url");
		makeBoldCell(headers.createCell(5), headerStyle, "Price");
		makeBoldCell(headers.createCell(6), headerStyle, "Option");
		makeBoldCell(headers.createCell(7), headerStyle, "Size");
		makeBoldCell(headers.createCell(8), headerStyle, "Count");
		makeBoldCell(headers.createCell(9), headerStyle, "Cost Each");
	}

	private static void makeBoldCell(Cell cell, CellStyle headerStyle, String val) {
		cell.setCellStyle(headerStyle);
		cell.setCellValue(val);
	}

	public void writeRow(Row row) {
		if (productType == ChewyUrl.PILL_TREATS.getCategory()) {
			System.out.println(this);
		}
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
