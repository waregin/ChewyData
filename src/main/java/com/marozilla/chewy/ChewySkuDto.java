package com.marozilla.chewy;

import java.util.HashMap;
import java.util.List;
import java.util.Map;

public class ChewySkuDto {
    int id;
    String partNumber;
    List<ChewyAttribute> definingAttributes;
    List<ChewyAttribute> descriptiveAttributes;
    Map<String, ChewyAttribute> descriptiveAttributesMap;
    List<ChewyAttribute> displayableAttribute;
    //customizableAttributesByGroup;
    boolean isDropShip;
    String name;
    String brand;
    String authorName;
    String publicationDate;
    String shortDesc;
    String longDescMd;
    String thumbnailImageMosaicUri;
    //fullImage
    //productId
    //canonicalCategoryId
    //pricing
    //rating
    //mosaicThumbnailUri
    //dimension
    //weight
    //keyBenefits
    //featuredPromotions
    //traits
    //isBuyable
    //inStock
    //autoshipAllowed
    //minShipDays
    //maxShipDays
    //deliveryMessageType
    //parentCatalogGroupIds
    //restrictedAvailability

    public void mapDescriptiveAttributes() {
        descriptiveAttributesMap = new HashMap<>();
        for (ChewyAttribute attribute : descriptiveAttributes) {
            descriptiveAttributesMap.put(attribute.identifier, attribute);
        }
    }

    @Override
    public String toString() {
        return "ChewySkuDto{" +
                "id=" + id +
                ", partNumber='" + partNumber + '\'' +
                ", definingAttributes=" + definingAttributes +
                ", descriptiveAttributes=" + descriptiveAttributes +
                ", displayableAttribute=" + displayableAttribute +
                ", isDropShip=" + isDropShip +
                ", name='" + name + '\'' +
                ", brand='" + brand + '\'' +
                ", authorName='" + authorName + '\'' +
                ", publicationDate='" + publicationDate + '\'' +
                ", shortDesc='" + shortDesc + '\'' +
                ", longDescMd='" + longDescMd + '\'' +
                ", thumbnailImageMosaicUri='" + thumbnailImageMosaicUri + '\'' +
                '}';
    }
}
