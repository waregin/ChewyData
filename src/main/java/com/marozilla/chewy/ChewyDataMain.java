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
import java.io.IOException;
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
	private static String currentProductType = "";

	public static void main(String[] args) {
		LocalDateTime today = LocalDateTime.now();
		XSSFWorkbook workbook = new XSSFWorkbook();
		String fileName = "src/main/resources/ChewyOutput" + today.format(DateTimeFormatter.ISO_LOCAL_DATE) + ".xlsx";
		try (FileOutputStream outputStream = new FileOutputStream(fileName)) {
			for (ChewyUrl url : ChewyUrl.values()) {
				int rowCount = 0;
				XSSFSheet sheet = workbook.createSheet(url.name());
				ChewyProduct.writeHeaders(sheet.createRow(rowCount++));

				currentProductType = url.getCategory();
				Document primaryPage = Jsoup.connect(url.getUrl()).get();

				Set<String> productUrlList = findProductUrls(primaryPage);
				Set<String> pageUrlList = generatePageUrlList(primaryPage);
				for (String pageUrl : pageUrlList) {
					productUrlList.addAll(findProductUrls(Jsoup.connect(pageUrl).get()));
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
			workbook.write(outputStream);
		} catch (IOException | InterruptedException e) {
			e.printStackTrace();
		}
	}

	private static Document connectWithErrorHandling(String url) throws InterruptedException {
		Document document = null;
		int weTried = 0;
		while (document == null && weTried < 5) {
			try {
				document = Jsoup.connect(url).get();
			} catch (Exception e) {
				System.out.println("Error connecting to " + url);
				e.printStackTrace();
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

	private static List<ChewyProduct> generateProductsFromOptions(boolean sizeMatters, String productUrl, Element options) throws IOException, InterruptedException {
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

				product.option = thisSkuDto.definingAttributes.get(0).value;
				for (ChewyAttribute attr : thisSkuDto.descriptiveAttributes) {
					if (attr.identifier.equalsIgnoreCase("SizeStandard")) {
						product.size = attr.value;
					}
					if (attr.identifier.equalsIgnoreCase("CountStandard")) {
						product.count = attr.value;
					}
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

		product.option = document.getElementsByAttributeValue("class", "ga-eec__variant").first().text();
		String[] splitName = product.itemName.split(" ");
		for (int i = 0; i < splitName.length; i++) {
			if (splitName[i].equalsIgnoreCase("count") && splitName[i-1].matches("-?\\d+")) {
				product.count = splitName[i-1];
			}
			if (splitName[i].toLowerCase().contains("oz") || splitName[i].toLowerCase().contains("lb")) {
				product.size = splitName[i];
			}
		}
		if (product.size.isEmpty() && product.option.toLowerCase().contains("oz") || product.option.toLowerCase().contains("lb")) {
			product.size = product.option.split(" ")[0];
		}
		if (product.count.isEmpty() && product.option.toLowerCase().contains("count")) {
			String[] splitOption = product.option.split(" ");
			for (int i = 0; i < splitOption.length; i++) {
				if (splitOption[i].equalsIgnoreCase("count") && splitOption[i-1].matches("-?\\d+")) {
					product.count = splitOption[i-1];
				}
			}
		}
		if (product.count.matches("-?\\d+")) {
			BigDecimal count = new BigDecimal(product.count);
			BigDecimal price = new BigDecimal(product.price.substring(1));
			NumberFormat nf = NumberFormat.getCurrencyInstance();
			product.pricePerEach = nf.format(price.divide(count, 2, RoundingMode.FLOOR));
		}

		return product;
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
