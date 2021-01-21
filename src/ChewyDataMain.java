import java.io.IOException;
import java.util.ArrayList;
import java.util.List;

import org.jsoup.Jsoup;
import org.jsoup.nodes.Document;
import org.jsoup.nodes.Element;
import org.jsoup.select.Elements;

public class ChewyDataMain {
	private static final boolean DOGS = true;
	private static final String SIZE_KEY = "\"identifier\":\"SizeStandard\",\"name\":\"Size Standard\",\"value\":\"";
	private static final String COUNT_KEY = "\"identifier\":\"CountStandard\",\"name\":\"Count Standard\",\"value\":\"";

	public static void main(String[] args) throws IOException {
		Document primaryPage = Jsoup.connect("https://www.chewy.com/b/dental-chews-1463").get();

		List<String> pageUrlList = generatePageUrlList(primaryPage);

		List<String> productUrlList = findProductUrls(primaryPage);
		for (String pageUrl : pageUrlList) {
			productUrlList.addAll(findProductUrls(Jsoup.connect(pageUrl).get()));
		}

		for (String productUrl : productUrlList) {
			Document document = Jsoup.connect(productUrl).get();
			if (DOGS && !isForBigDogs(document)) {
				continue;
			}

			Element options = document.getElementById("vue-portal__sfw-attribute-buttons");
			if (options != null) {
				generateProductsFromOptions(productUrl, options);
			} else {
				System.out.println(generateProduct(productUrl, document));
			}
		}
	}

	private static List<String> generatePageUrlList(Document primaryPage) {
		List<String> pageUrlList = new ArrayList<>();
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

	private static void generateProductsFromOptions(String productUrl, Element options) throws IOException {
		String baseUrl = productUrl.substring(0, productUrl.lastIndexOf("/") + 1);
		String attributes = options.attr("data-attributes");
		attributes = attributes.substring(attributes.indexOf("attributeValues"));
		while (attributes.indexOf("skuDto") != -1) {
			String skuDto = "skuDto\":{\"id\":";
			attributes = attributes.substring(attributes.indexOf(skuDto) + skuDto.length());
			String sku = attributes.substring(0, attributes.indexOf(","));
			String url = baseUrl + sku;

			Document option = Jsoup.connect(url).get();
			if (DOGS && !isForBigDogs(option)) {
				continue;
			}
			ChewyProduct product = generateProduct(url, option);

			String value = "\"value\":\"";
			attributes = attributes.substring(attributes.indexOf(value) + value.length());
			product.option = attributes.substring(0, attributes.indexOf("\""));

			int endIndex = attributes.indexOf("skuDto");
			String sizeString;
			String countString;
			if (endIndex > 0) {
				countString = sizeString = attributes.substring(0, endIndex);
			} else {
				countString = sizeString = attributes;
			}
			countString = countString.substring(countString.indexOf(COUNT_KEY) + COUNT_KEY.length());
			product.count = countString.substring(0, countString.indexOf("\""));
			sizeString = sizeString.substring(sizeString.indexOf(SIZE_KEY) + SIZE_KEY.length());
			product.size = sizeString.substring(0, sizeString.indexOf("\""));

			System.out.println(product);
		}
	}

	private static boolean isForBigDogs(Document document) {
		boolean recordProduct = false;
		Elements attributesList = document.getElementById("attributes").child(0).children();
		for (Element attribute : attributesList) {
			if (attribute.child(0).text().equals("Breed Size")) {
				recordProduct = attribute.child(1).text().contains("Large Breeds")
						|| attribute.child(1).text().contains("Giant Breeds");
				break;
			}
		}
		return recordProduct;
	}

	private static ChewyProduct generateProduct(String productUrl, Document document) {
		ChewyProduct product = new ChewyProduct();
		product.URL = productUrl;

		Element productName = document.getElementsByAttributeValue("id", "product-title").first();
		product.brandName = productName.child(1).child(0).child(0).text();
		product.itemName = productName.child(0).text().replace(product.brandName, "").trim();

		product.price = document.getElementsByAttributeValue("class", "ga-eec__price").first().text();

		String[] splits = product.URL.split("/");
		product.sku = splits[splits.length - 1];

		product.imageUrl = document.getElementsByAttributeValue("id", "Zoomer").first().child(0).attr("data-src");

		Element findOption = document.getElementById("variation-Count");
		if (findOption == null) {
			findOption = document.getElementById("variation-Size");
		}
		if (findOption != null) {
			product.option = findOption.getElementsByAttributeValue("class", "attribute-selection__value").first()
					.text();
		}

		return product;
	}

	private static List<String> findProductUrls(Document document) {
		List<String> productUrlList = new ArrayList<>();
		Elements productCardItems = document.getElementsByAttributeValue("class",
				"product-holder js-tracked-product  cw-card cw-card-hover");
		for (Element productCard : productCardItems) {
			productUrlList.add(productCard.child(0).attr("abs:href"));
		}
		return productUrlList;
	}

}
