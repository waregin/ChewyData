package com.marozilla.chewy;

public class ChewyAttribute {
    String identifier;
    String name;
    String value;

    @Override
    public String toString() {
        return "ChewyAttribute{" +
                "identifier='" + identifier + '\'' +
                ", name='" + name + '\'' +
                ", value='" + value + '\'' +
                '}';
    }
}
