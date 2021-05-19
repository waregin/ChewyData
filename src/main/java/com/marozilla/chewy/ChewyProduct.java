package com.marozilla.chewy;

import org.apache.poi.ss.usermodel.Cell;
import org.apache.poi.ss.usermodel.CellStyle;
import org.apache.poi.ss.usermodel.Font;
import org.apache.poi.ss.usermodel.Row;

public class ChewyProduct {
	String SEPARATOR = "|";
	ChewyUrl productType;
	String url = "";
	String brandName = "";
	String itemName = "";
	String sku = "";
	String imageUrl = "";
	String protein = "";
	String fat = "";
	String fiber = "";
	String moisture = "";
	String feedingInstructions = "";
	String price = "";
	String option = "";
	String size = "";
	String count = "";
	String pricePerEach = "";

	public static void writeHeaders(Row headers, ChewyUrl chewyUrl) {
		CellStyle headerStyle = headers.getSheet().getWorkbook().createCellStyle();
		Font font = headers.getSheet().getWorkbook().createFont();
		font.setBold(true);
		headerStyle.setFont(font);

		int i = 0;
		makeBoldCell(headers.createCell(i++), headerStyle, "URL");
		makeBoldCell(headers.createCell(i++), headerStyle, "Brand Name");
		makeBoldCell(headers.createCell(i++), headerStyle, "Item Name");
		makeBoldCell(headers.createCell(i++), headerStyle, "SKU");
		makeBoldCell(headers.createCell(i++), headerStyle, "Image Url");
		if (chewyUrl.isWantNutrition()) {
			makeBoldCell(headers.createCell(i++), headerStyle, "Protein");
			makeBoldCell(headers.createCell(i++), headerStyle, "Fat");
			makeBoldCell(headers.createCell(i++), headerStyle, "Fiber");
			makeBoldCell(headers.createCell(i++), headerStyle, "Moisture");
		}
		if (chewyUrl.isWantFeeding()) {
			makeBoldCell(headers.createCell(i++), headerStyle, "Feeding Instructions");
		}
		makeBoldCell(headers.createCell(i++), headerStyle, "Price");
		makeBoldCell(headers.createCell(i++), headerStyle, "Option");
		makeBoldCell(headers.createCell(i++), headerStyle, "Size");
		makeBoldCell(headers.createCell(i++), headerStyle, "Count");
		makeBoldCell(headers.createCell(i), headerStyle, "Cost Each");
	}

	private static void makeBoldCell(Cell cell, CellStyle headerStyle, String val) {
		cell.setCellStyle(headerStyle);
		cell.setCellValue(val);
	}

	public void writeRow(Row row) {
		int i = 0;
		row.createCell(i++).setCellValue(url);
		row.createCell(i++).setCellValue(brandName);
		row.createCell(i++).setCellValue(itemName);
		row.createCell(i++).setCellValue(sku);
		row.createCell(i++).setCellValue(imageUrl);
		if (productType.isWantNutrition()) {
			row.createCell(i++).setCellValue(protein);
			row.createCell(i++).setCellValue(fat);
			row.createCell(i++).setCellValue(fiber);
			row.createCell(i++).setCellValue(moisture);
		}
		if (productType.isWantFeeding()) {
			row.createCell(i++).setCellValue(feedingInstructions);
		}
		row.createCell(i++).setCellValue(price);
		row.createCell(i++).setCellValue(option);
		row.createCell(i++).setCellValue(size);
		row.createCell(i++).setCellValue(count);
		row.createCell(i).setCellValue(pricePerEach);
	}

	@Override
	public String toString() {
		return productType + SEPARATOR + url + SEPARATOR + brandName + SEPARATOR + itemName + SEPARATOR + sku
				+ SEPARATOR + imageUrl + SEPARATOR + protein + SEPARATOR + fat + SEPARATOR + fiber + SEPARATOR + moisture
				+ SEPARATOR + feedingInstructions + SEPARATOR + price + SEPARATOR + option + SEPARATOR + size + SEPARATOR + count
				+ SEPARATOR + pricePerEach;
	}
}
