package com.marozilla.chewy;

public enum ChewyUrl {
    PILL_TREATS("Pill Treats", "https://www.chewy.com/b/pill-covers-wraps-2693", false, false, false),
    DENTAL("Dental", "https://www.chewy.com/b/dental-chews-1463", true, false, true),
    BULLY_STICK("Bully Sticks", "https://www.chewy.com/b/bully-sticks-1543", true, false, false),
    BONE("Bones","https://www.chewy.com/b/bones-1542", true, false, false),
    RAWHIDE("Rawhide", "https://www.chewy.com/b/rawhide-1545", true, false, false),
    ANTLER("Antlers", "https://www.chewy.com/b/antlers-1541", true, false, false),
    HIMA_CHEW("Himalayan Chews", "https://www.chewy.com/b/himalayan-chews-2780", true, false, false),
    NATURAL_CHEW("Natural Chews", "https://www.chewy.com/b/natural-chews-1544", true, false, false),
    RAWHIDE_ALT("Rawhide Alternatives", "https://www.chewy.com/b/rawhide-alternatives-9939", true, false, false),
    HARD_CHEW("Hard Chews", "https://www.chewy.com/b/hard-chews-9938", true, false, false),
    DOG_FOOD("Dog Food", "https://www.chewy.com/b/food-332", true, true, true),
    DRY_CAT_FOOD("Dry Cat Food", "https://www.chewy.com/b/dry-food-388", false, true, true),
    PREMIUM_CAT_FOOD("Premium Cat Food", "https://www.chewy.com/b/premium-food-11741", false, true, true),
    WET_CAT_FOOD("Canned Cat Food", "https://www.chewy.com/b/wet-food-389", false, true, true),
    RAW_CAT_FOOD("Raw Cat Food", "https://www.chewy.com/b/raw-food-8434", false, true, true),
    DRIED_CAT_FOOD("Freeze Dried Dehydrated Cat Food", "https://www.chewy.com/b/freeze-dried-dehydrated-food-11737", false, true, true);

    private final String category;
    private final String url;
    private final boolean sizeMatters;
    private final boolean wantNutrition;
    private final boolean wantFeeding;

    ChewyUrl(String category, String url, boolean sizeMatters, boolean wantNutrition, boolean wantFeeding) {
        this.category = category;
        this.url = url;
        this.sizeMatters = sizeMatters;
        this.wantNutrition = wantNutrition;
        this.wantFeeding = wantFeeding;
    }

    public String getCategory() {
        return category;
    }

    public String getUrl() {
        return url;
    }

    public boolean isSizeMatters() {
        return sizeMatters;
    }

    public boolean isWantNutrition() {
        return wantNutrition;
    }

    public boolean isWantFeeding() {
        return wantFeeding;
    }
}
