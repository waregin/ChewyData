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
import java.util.ArrayList;
import java.util.HashSet;
import java.util.List;
import java.util.Set;

public class ChewyDataMain {
	private static final Set<String> skus = new HashSet<>();
	private static final Gson gson = new Gson();
	private static ChewyUrl currentProductType;
	private static String currentUrl;

	public static void main(String[] args) {
		LocalDateTime today = LocalDateTime.now();
		System.out.println("Starting program at: " + today);
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

					for (String productUrl : productUrlList) {
						Document document = connectWithErrorHandling(productUrl);

						Element options = document.getElementById("vue-portal__sfw-attribute-buttons");
						if (options != null) {
							List<ChewyProduct> products = generateProductsFromOptions(url.isSizeMatters(), productUrl, options);
							for (ChewyProduct product : products) {
								product.writeRow(sheet.createRow(rowCount++));
							}
						} else {
							if (url.isSizeMatters() && isNotForBigDogs(document)) {
								continue;
							}
							ChewyProduct chewyProduct = generateProduct(productUrl, document);
							chewyProduct.writeRow(sheet.createRow(rowCount++));
							if (skus.size()%50 == 0) {
								System.out.println(skus.size());
							}
						}
					}
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
		System.out.println(LocalDateTime.now() + " All Done!");
	}

	private static Document connectWithErrorHandling(String url) throws InterruptedException {
		Document document = null;
		int weTried = 0;
		while (document == null && weTried < 5) {
			try {
				document = Jsoup.connect(url).get();
			} catch (Exception e) {
				System.out.println("Error connecting to " + url + " : " + e.getMessage());
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
				"pagination_selection cw-pagination__item");
		if (paginationItems.size() > 1) {
			int numPages = Integer.parseInt(paginationItems.last().text());
			String pageTwoUrl = paginationItems.first().attr("href");
			pageUrlList.add("https://www.chewy.com" + pageTwoUrl);
			for (int i = 3; i <= numPages; i++) {
				String pageUrl = pageTwoUrl.replace("p2", "p" + i);
				pageUrlList.add("https://www.chewy.com" + pageUrl);
			}
		}
		return pageUrlList;
	}

	private static List<ChewyProduct> generateProductsFromOptions(boolean sizeMatters,
																  String productUrl, Element options) throws InterruptedException {
		List<ChewyProduct> products = new ArrayList<>();

		String baseUrl = productUrl.substring(0, productUrl.lastIndexOf("/") + 1);
		String attributes = options.attr("data-attributes");
		Type founderListType = new TypeToken<ArrayList<ChewyProductAttributes>>(){}.getType();
		List<ChewyProductAttributes> attributesList = gson.fromJson(attributes, founderListType);
		for (ChewyProductAttributes chewyProductAttributes : attributesList) {
			for (AttributeValue attributeValue : chewyProductAttributes.attributeValues) {
				ChewySkuDto thisSkuDto = attributeValue.skuDto;
				if (thisSkuDto == null) {
					continue;
				}
				thisSkuDto.mapDescriptiveAttributes();
				ChewyAttribute breedSize = thisSkuDto.descriptiveAttributesMap.get("BreedSize");
				if ((sizeMatters && breedSize != null && isNotForBigDogs(breedSize))
						|| !skus.add("" + thisSkuDto.id)) {
					continue;
				}

				String url = baseUrl + thisSkuDto.id;
				Document document = connectWithErrorHandling(url);
				ChewyProduct product = generateProduct(url, document);

				if (product.option.isEmpty()) {
					product.option = thisSkuDto.definingAttributes.get(0).value;
					findCount(product);
				} else {
					product.option = thisSkuDto.definingAttributes.get(0).value;
				}
				for (ChewyAttribute attr : thisSkuDto.descriptiveAttributes) {
					if (product.size.isEmpty() && attr.identifier.equalsIgnoreCase("SizeStandard")) {
						product.size = attr.value;
					}
					if (product.count.isEmpty() && attr.identifier.equalsIgnoreCase("CountStandard")) {
						product.count = attr.value;
					}
				}
				if (product.pricePerEach.isEmpty()) {
					findPricePerEach(product);
				}
				products.add(product);
				if (skus.size()%50 == 0) {
					System.out.println(skus.size());
				}
			}
		}

		return products;
	}

	private static boolean isNotForBigDogs(ChewyAttribute breedSize) {
		return !(breedSize.value.contains("Large Breeds") || breedSize.value.contains("Giant Breeds"));
	}

	private static boolean isNotForBigDogs(Document document) {
		boolean recordProduct = false;
		Element attributes = document.getElementById("attributes");
		if (attributes == null) {
			return false;
		}
		Elements attributesList = attributes.child(0).children();
		for (Element attribute : attributesList) {
			if (attribute.child(0).text().equals("Breed Size")) {
				recordProduct = attribute.child(1).text().contains("Large Breeds")
						|| attribute.child(1).text().contains("Giant Breeds");
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

		Element productName = document.getElementsByAttributeValue("id", "product-title").first();
		product.brandName = productName.child(1).child(0).child(0).text();
		product.itemName = productName.child(0).text().replace(product.brandName, "").trim();

		product.price = document.getElementsByAttributeValue("class", "ga-eec__price").first().text();

		String[] splits = product.url.split("/");
		product.sku = splits[splits.length - 1];
		skus.add(product.sku);

		product.imageUrl = document.getElementsByAttributeValue("id", "Zoomer").first().child(0).attr("data-src");

		if (currentProductType.isWantNutrition()) {
			Element nutIn = document.getElementById("Nutritional-Info");
			if (nutIn != null) {
				Elements nutritionalInfo = nutIn.getElementsByTag("td");
				if (nutritionalInfo.size() >= 8) {
					product.protein = nutritionalInfo.get(1).text();
					product.fat = nutritionalInfo.get(3).text();
					product.fiber = nutritionalInfo.get(5).text();
					product.moisture = nutritionalInfo.get(7).text();
				}
			}
		}
		if (currentProductType.isWantFeeding()) {
			Element feedingInstructions = document.getElementById("Feeding-Instructions");
			if (feedingInstructions != null) {
				product.feedingInstructions = feedingInstructions.child(1).wholeText();
			}
		}

		product.option = document.getElementsByAttributeValue("class", "ga-eec__variant").first().text();
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
		if (product.option.toLowerCase().contains("case of")) {
			if (splitOption.length == 5 && isNumber(splitOption[0]) && isNumber(splitOption[4])) {
				product.count = String.valueOf(Integer.parseInt(splitOption[0]) * Integer.parseInt(splitOption[4]));
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
				"product-holder js-tracked-product  cw-card cw-card-hover");
		for (Element productCard : productCardItems) {
			productUrlList.add(productCard.child(0).attr("abs:href"));
		}
		return productUrlList;
	}

}
