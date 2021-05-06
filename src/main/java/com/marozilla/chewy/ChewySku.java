package com.marozilla.chewy;

import java.util.List;

public class ChewySku {
    int id;
    String type;
    String partNumber;
    String name;
    String longDescription;
    String thumbnail;
    String fullImage;
    List<ChewyPrice> price;
    String manufacturer;
    String manufacturerPartNumber;
    String gtin;
    String keywords;
    int parentCatalogEntryId;
    List<Integer> parentCatalogGroupId;
    boolean published;
    boolean buyable;
    //startDate
    //lastUpdate
    //rating
    //ratingCount
    //packaging
    //attachmentasset
    //attribute
    //userData
    //inStock
    //parentPartNumber
    //autoshipPromotionId
    //customizableFacet
    //backorderable
    //mapEnforcedType
    //catalogEntryPromotion
    //newCatenttype

    @Override
    public String toString() {
        return "ChewySku{" +
                "id=" + id +
                ", type='" + type + '\'' +
                ", partNumber='" + partNumber + '\'' +
                ", name='" + name + '\'' +
                ", longDescription='" + longDescription + '\'' +
                ", thumbnail='" + thumbnail + '\'' +
                ", fullImage='" + fullImage + '\'' +
                ", price=" + price +
                ", manufacturer='" + manufacturer + '\'' +
                ", manufacturerPartNumber='" + manufacturerPartNumber + '\'' +
                ", gtin='" + gtin + '\'' +
                ", keywords='" + keywords + '\'' +
                ", parentCatalogEntryId=" + parentCatalogEntryId +
                ", parentCatalogGroupId=" + parentCatalogGroupId +
                ", published=" + published +
                ", buyable=" + buyable +
                '}';
    }
}
