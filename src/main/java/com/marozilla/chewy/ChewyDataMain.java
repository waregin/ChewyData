package com.marozilla.chewy;

import com.google.gson.Gson;
import com.google.gson.reflect.TypeToken;
import org.apache.poi.xssf.usermodel.XSSFSheet;
import org.apache.poi.xssf.usermodel.XSSFWorkbook;
import org.jsoup.Jsoup;
import org.jsoup.nodes.Document;
import org.jsoup.nodes.Element;
import org.jsoup.select.Elements;

import java.io.FileOutputStream;
import java.lang.reflect.Type;
import java.math.BigDecimal;
import java.math.RoundingMode;
import java.text.NumberFormat;
import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.util.*;

public class ChewyDataMain {
	private static Set<String> skus = new HashSet<>();
	private static Set<String> completeUrlSet = new HashSet<>();
	private static ChewyUrl currentProductType;
	private static String currentUrl;
	private static int num404s = 0;

	public static void main(String[] args) {
		LocalDateTime today = LocalDateTime.now();
		System.out.println("Starting program at: " + today);
		int productUrlsProcessed = 0;
		int productUrlsTotal = 0;
		int optionUrlsProcessed = 0;
		int optionUrlListTotal = 0;
		XSSFWorkbook workbook = new XSSFWorkbook();
		workbook.createFont();
		String fileName = "src/main/resources/ChewyOutput" + today.format(DateTimeFormatter.ISO_LOCAL_DATE) + ".xlsx";
		try (FileOutputStream outputStream = new FileOutputStream(fileName)) {
			try {
				for (ChewyUrl url : ChewyUrl.values()) {
					int rowCount = 0;
					XSSFSheet sheet = workbook.createSheet(url.getCategory());
					ChewyProduct.writeHeaders(sheet.createRow(rowCount++), url);

					currentProductType = url;
					Document primaryPage = connectWithErrorHandling(url.getUrl());

					Set<String> productUrlList = findProductUrls(primaryPage);
					Set<String> pageUrlList = generatePageUrlList(primaryPage);
					for (String pageUrl : pageUrlList) {
						productUrlList.addAll(findProductUrls(connectWithErrorHandling(pageUrl)));
					}

					productUrlsTotal += productUrlList.size();
					for (String productUrl : productUrlList) {
						productUrlsProcessed++;
						Document document = connectWithErrorHandling(productUrl);

						Set<String> optionUrlList = generateProductUrlsFromOptions(productUrl, document);
						optionUrlList.removeAll(productUrlList);
						optionUrlList.add(productUrl);
						optionUrlListTotal += optionUrlList.size();

						for (String optionUrl : optionUrlList) {
							optionUrlsProcessed++;
							String sku = optionUrl.substring(optionUrl.lastIndexOf("/") + 1);
							if (!skus.add(sku) && !completeUrlSet.add(optionUrl)) {
								continue;
							}
							if (!optionUrl.equals(document != null ? document.baseUri() : null)) {
								document = connectWithErrorHandling(optionUrl);
							}

							if (document == null || (url.isSizeMatters() && isNotForBigDogs(document))) {
								continue;
							}

							ChewyProduct chewyProduct = generateProduct(optionUrl, document);
							if (chewyProduct == null) {
								continue;
							}
							chewyProduct.writeRow(sheet.createRow(rowCount++));
							if (skus.size()%50 == 0 || completeUrlSet.size()%50 == 0) {
								System.out.println(LocalDateTime.now() + "\n   num skus: " + skus.size()
										+ "\n   num complete URLs: " + completeUrlSet.size()
										+ "\n   product urls processed: " + productUrlsProcessed
										+ "\n   option urls processed: " + optionUrlsProcessed);
							}
						}
					}
					System.out.println("We got " + num404s + " 404 errors processing " + url.getCategory());
					System.out.println(LocalDateTime.now() + "\n   num skus: " + skus.size()
							+ "\n   num complete URLs: " + completeUrlSet.size()
							+ "\n   product urls total: " + productUrlsTotal
							+ "\n   product urls processed: " + productUrlsProcessed
							+ "\n   option urls total: " + optionUrlListTotal
							+ "\n   option urls processed: " + optionUrlsProcessed);
					num404s = 0;
					skus = new HashSet<>();
					completeUrlSet = new HashSet<>();
				}
			} catch (Exception e) {
				System.out.println("Error in " + currentUrl);
				e.printStackTrace();
			}
			workbook.write(outputStream);
		} catch (Exception e) {
			System.out.println("Error!");
			e.printStackTrace();
		}
	}

	private static Set<String> generateProductUrlsFromOptions(String productUrl, Document document) {
		Set<String> productUrls = new HashSet<>();
		String baseUrl = productUrl.substring(0, productUrl.lastIndexOf("/") + 1);

		Elements chipOptionElements = document.getElementsByAttributeValue("class", "kib-chip-choice__control");
		Elements dropdownOptionElements = document.getElementsByAttributeValue("data-testid", "dropdown-radio-input");
		Elements iterateOptions = chipOptionElements;
		iterateOptions.addAll(dropdownOptionElements);
		for (Element e : iterateOptions) {
			String value = e.val();
			if (!value.isEmpty()) {
				productUrls.add(baseUrl + value);
			}
		}

		return productUrls;
	}

	private static Document connectWithErrorHandling(String url) throws InterruptedException {
		Document document = null;
		int weTried = 0;
		while (document == null && weTried < 5) {
			try {
				document = Jsoup.connect(url).get();
			} catch (Exception e) {
				if (e.toString().toLowerCase().contains("status=404")) {
					num404s++;
					return null;
				}
				System.out.println("Error connecting to " + url + " : " + e);
				Thread.sleep(15000);
			} finally {
				weTried++;
			}
		}
		return document;
	}

	private static Set<String> generatePageUrlList(Document primaryPage) {
		Set<String> pageUrlList = new HashSet<>();
		Elements paginationItems = primaryPage.getElementsByAttributeValue("class",
				"kib-pagination-new__list-item");
		if (paginationItems.size() > 1) {
			int numPages = Integer.parseInt(paginationItems.last().text());
			String pageTwoUrl = paginationItems.get(1).child(0).attr("href");
			pageUrlList.add("https://www.chewy.com" + pageTwoUrl);
			for (int i = 3; i <= numPages; i++) {
				String pageUrl = pageTwoUrl.replace("p2", "p" + i);
				pageUrlList.add("https://www.chewy.com" + pageUrl);
			}
		}
		return pageUrlList;
	}

	private static boolean isNotForBigDogs(Document document) {
		Elements tableRows = document.getElementsByTag("tr");
		if (tableRows == null || tableRows.size() == 0) {
			return false;
		}
		boolean recordProduct = false;
		for (Element row : tableRows) {
			if (row.childrenSize() == 2 && row.child(0).text().equals("Breed Size")) {
				recordProduct = row.child(1).text().contains("Large Breeds")
						|| row.child(1).text().contains("Giant Breeds");
				break;
			}
		}
		return !recordProduct;
	}

	private static ChewyProduct generateProduct(String productUrl, Document document) {
		currentUrl = productUrl;
		ChewyProduct product = new ChewyProduct();
		product.productType = currentProductType;
		product.url = productUrl;
		product.sku = productUrl.substring(productUrl.lastIndexOf("/") + 1);

		Element productName = document.getElementsByAttributeValue("data-testid", "product-title").first();
		if (productName == null) {
			return null;
		}
		product.brandName = productName.child(1).child(0).child(0).text();
		product.itemName = productName.child(0).text().replace(product.brandName, "").trim();

		product.price = document.getElementsByAttributeValue("data-testid", "advertised-price").first().text().replace("Chewy Price", "");


		product.imageUrl = document.getElementsByAttributeValue("class", "styles_mainCarouselImage__wj_bU").first().attr("src");

		if (currentProductType.isWantNutrition()) {
			if (document.getElementById("INGREDIENTS-section") != null) {
				String ingredients = document.getElementById("INGREDIENTS-section").wholeText().toLowerCase();
				for (String item : SamsonAllergensList.LIST) {
					if (ingredients.contains(item)) {
						product.containsSamsonAllergen = "true";
						break;
					}
				}
				if (product.containsSamsonAllergen.isEmpty()) {
					product.containsSamsonAllergen = "false";
				}
			}

			Element nutIn = document.getElementById("GUARANTEED_ANALYSIS-section");
			if (nutIn != null) {
				Elements nutritionalInfo = nutIn.getElementsByTag("tr");
				for (Element infoItem : nutritionalInfo) {
					if (infoItem.childrenSize() > 1) {
						String label = infoItem.child(0).text().toLowerCase();
						String value = infoItem.child(1).text();
						if (label.contains("protein")) {
							product.protein = value;
						} else if (label.contains("fat")) {
							product.fat = value;
						} else if (label.contains("fiber")) {
							product.fiber = value;
						} else if (label.contains("moisture")) {
							product.moisture = value;
						}
					}
				}
			}
		}
		if (currentProductType.isWantFeeding()) {
			Element feedingInstructions = document.getElementById("FEEDING_INSTRUCTIONS-section");
			if (feedingInstructions != null) {
				product.feedingInstructions = feedingInstructions.child(0).wholeText().strip();
			}
		}

		Elements optionElements = document.getElementsByAttributeValue("class", "styles_dropdownSelectorContainer__SBhgm");
		Element optionElement = null;
		if (optionElements.size() > 0) {
			optionElement = optionElements.stream().filter(element ->
					element.getElementsByAttributeValue("class", "kib-form-dropdown__label")
							.first().text().contains("Size")).findFirst().orElse(null);
			if (optionElement != null) {
				optionElement = optionElement.getElementsByAttribute("checked").parents()
						.first().getElementsByAttributeValue("class", "kib-radio__label").first();
			}
		} else {
			optionElements = document.getElementsByAttributeValue("class", "styles_chipSelectorContainer__AEhGg");
			if (optionElements.size() > 0) {
				optionElement = optionElements.stream().filter(element ->
						element.getElementsByAttributeValue("class", "styles_chipSelectorHeader__pKnJG kib-typography-paragraph1")
								.first().text().contains("Size")).findFirst().orElse(null);
				if (optionElement != null) {
					optionElement = optionElement.getElementsByAttributeValue("aria-checked", "true")
							.first().getElementsByAttributeValue("class", "styles_chipLabel__cJRBM").first();
				}
			}
		}
		if (optionElement != null) {
			product.option = optionElement.text();
		}
		findCount(product);
		String[] splitName = product.itemName.split(" ");
		for (String s : splitName) {
			if (s.toLowerCase().contains("oz") || s.toLowerCase().contains("lb")) {
				product.size = s;
			}
		}
		if (product.size.isEmpty() && product.option.toLowerCase().contains("oz") || product.option.toLowerCase().contains("lb")) {
			product.size = product.option.split(" ")[0];
		}

		return product;
	}

	private static void findCount(ChewyProduct product) {
		String[] splitName = product.itemName.split(" ");
		for (int i = 0; i < splitName.length; i++) {
			if (i > 0 && (splitName[i].equalsIgnoreCase("count")
					|| splitName[i].equalsIgnoreCase("count,")) && isNumber(splitName[i-1])) {
				int previousCount = 1;
				try {
					previousCount = Integer.parseInt(product.count);
				} catch (NumberFormatException e) {
					// ignore quietly
				}
				product.count = String.valueOf(previousCount * Integer.parseInt(splitName[i-1]));
			}
		}
		String[] splitOption = product.option.split(" ");
		if (product.count.isEmpty() && product.option.toLowerCase().contains("count")) {
			for (int i = 1; i < splitOption.length; i++) {
				if (splitOption[i].toLowerCase().contains("count") && isNumber(splitOption[i-1])) {
					product.count = splitOption[i-1];
				}
			}
		}
		if (product.productType.equals(ChewyUrl.PILL_TREATS) && product.count.isEmpty()) {
			if (product.option.toLowerCase().contains("capsule") || product.option.toLowerCase().contains("tablet")) {
				for (int i = 1; i < splitOption.length; i++) {
					if ((splitOption[i].toLowerCase().contains("capsule")
							|| splitOption[i].toLowerCase().contains("tablet")) && isNumber(splitOption[i-1])) {
						product.count = splitOption[i-1];
					}
				}
			}
		}
		if (product.option.toLowerCase().contains("case of") && splitOption.length == 5 && isNumber(splitOption[4])) {
			if (isNumber(splitOption[0])) {
				product.count = String.valueOf(Integer.parseInt(splitOption[0]) * Integer.parseInt(splitOption[4]));
			} else if (product.productType.equals(ChewyUrl.WET_CAT_FOOD)) {
				product.count = splitOption[4];
			}
		}
		findPricePerEach(product);
	}

	private static void findPricePerEach(ChewyProduct product) {
		if (isNumber(product.count)) {
			BigDecimal count = new BigDecimal(product.count);
			BigDecimal price = new BigDecimal(product.price.substring(1));
			NumberFormat nf = NumberFormat.getCurrencyInstance();
			product.pricePerEach = nf.format(price.divide(count, 2, RoundingMode.FLOOR));
		}
	}

	private static boolean isNumber(String s) {
		return s.matches("-?\\d+");
	}

	private static Set<String> findProductUrls(Document document) {
		Set<String> productUrlList = new HashSet<>();
		Elements productCardItems = document.getElementsByAttributeValue("class",
				"kib-product-card ProductListing_kibProductCard__qXL4s js-tracked-product");
		for (Element productCard : productCardItems) {
			productUrlList.add(productCard.child(0).child(0).attr("abs:href"));
		}
		return productUrlList;
	}

}
