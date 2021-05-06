package com.marozilla.chewy;

import java.util.List;

public class ChewyProductAttributes {
    int id;
    double sequence;
    String name;
    String identifier;
    List<AttributeValue> attributeValues;

    @Override
    public String toString() {
        return "ChewyProductAttributes{" +
                "id=" + id +
                ", sequence=" + sequence +
                ", name='" + name + '\'' +
                ", identifier='" + identifier + '\'' +
                ", attributeValues=" + attributeValues +
                '}';
    }
}
