package com.marozilla.chewy;

public class AttributeValue {
    int id;
    int attributeId;
    double sequence;
    String value;
    boolean isSelected;
    boolean isAvailable;
    ChewySku sku;
    ChewySkuDto skuDto;

    @Override
    public String toString() {
        return "AttributeValue{" +
                "id=" + id +
                ", attributeId=" + attributeId +
                ", sequence=" + sequence +
                ", value='" + value + '\'' +
                ", isSelected=" + isSelected +
                ", isAvailable=" + isAvailable +
                ", sku=" + sku +
                ", skuDto=" + skuDto +
                '}';
    }
}
