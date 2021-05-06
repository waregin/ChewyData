package com.marozilla.chewy;

import com.google.gson.Gson;
import com.google.gson.reflect.TypeToken;
import org.jsoup.Jsoup;
import org.jsoup.nodes.Document;
import org.jsoup.nodes.Element;
import org.jsoup.select.Elements;

import java.io.File;
import java.io.FileWriter;
import java.io.IOException;
import java.lang.reflect.Type;
import java.math.BigDecimal;
import java.math.RoundingMode;
import java.text.NumberFormat;
import java.util.*;

public class ChewyDataMain {
	private static final boolean DOGS = true;
	private static final Set<String> skus = new HashSet<>();
	private static final Gson gson = new Gson();

	public static void main(String[] args) throws IOException {
		Document primaryPage = Jsoup.connect("https://www.chewy.com/b/dental-chews-1463").get();

		Set<String> pageUrlList = generatePageUrlList(primaryPage);

		Set<String> productUrlList = findProductUrls(primaryPage);
		for (String pageUrl : pageUrlList) {
			productUrlList.addAll(findProductUrls(Jsoup.connect(pageUrl).get()));
		}

		for (String productUrl : productUrlList) {
			Document document = Jsoup.connect(productUrl).get();
//			String[] splits = productUrl.split("/");
//			String fileName = splits[splits.length - 1] + ".html";
//			FileWriter fileWriter = new FileWriter(fileName);
//			fileWriter.write(document.toString());
//			fileWriter.close();

			Element options = document.getElementById("vue-portal__sfw-attribute-buttons");
			if (options != null) {
				generateProductsFromOptions(productUrl, options);
			} else {
				if (DOGS && isNotForBigDogs(document)) {
					continue;
				}
				System.out.println(generateProduct(productUrl, document));
			}
		}
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

	private static void generateProductsFromOptions(String productUrl, Element options) throws IOException {
		String baseUrl = productUrl.substring(0, productUrl.lastIndexOf("/") + 1);
		String attributes = options.attr("data-attributes");
		Type founderListType = new TypeToken<ArrayList<ChewyProductAttributes>>(){}.getType();
		List<ChewyProductAttributes> attributesList = gson.fromJson(attributes, founderListType);
		for (ChewyProductAttributes chewyProductAttributes : attributesList) {
			for (AttributeValue attributeValue : chewyProductAttributes.attributeValues) {
				ChewySkuDto thisSkuDto = attributeValue.skuDto;
				if (thisSkuDto == null || !skus.add("" + thisSkuDto.id)) {
					continue;
				}
				thisSkuDto.mapDescriptiveAttributes();
				if (DOGS && isNotForBigDogs(thisSkuDto.descriptiveAttributesMap.get("BreedSize"))) {
					continue;
				}

				String url = baseUrl + thisSkuDto.id;
				ChewyProduct product = generateProduct(url, Jsoup.connect(url).get());

				product.option = thisSkuDto.definingAttributes.get(0).value;
				for (ChewyAttribute attr : thisSkuDto.descriptiveAttributes) {
					if (attr.identifier.equalsIgnoreCase("SizeStandard")) {
						product.size = attr.value;
					}
					if (attr.identifier.equalsIgnoreCase("CountStandard")) {
						product.count = attr.value;
					}
				}
				System.out.println(product);
			}
		}
	}

	private static boolean isNotForBigDogs(ChewyAttribute breedSize) {
		return !(breedSize.value.contains("Large Breeds") || breedSize.value.contains("Giant Breeds"));
	}

	private static boolean isNotForBigDogs(Document document) {
		boolean recordProduct = false;
		Elements attributesList = document.getElementById("attributes").child(0).children();
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
		product.URL = productUrl;

		Element productName = document.getElementsByAttributeValue("id", "product-title").first();
		product.brandName = productName.child(1).child(0).child(0).text();
		product.itemName = productName.child(0).text().replace(product.brandName, "").trim();

		product.price = document.getElementsByAttributeValue("class", "ga-eec__price").first().text();

		String[] splits = product.URL.split("/");
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
