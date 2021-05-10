package com.marozilla.chewy;

public enum ChewyUrl {
    PILL_TREATS(PetType.DOG, "Pill Treats", "https://www.chewy.com/b/pill-covers-wraps-2693", false, false),
    DENTAL(PetType.DOG, "Dental", "https://www.chewy.com/b/dental-chews-1463", false, true),
    BULLY_STICK(PetType.DOG, "Bully Sticks", "https://www.chewy.com/b/bully-sticks-1543", false, false),
    BONE(PetType.DOG, "Bones","https://www.chewy.com/b/bones-1542", false, false),
    RAWHIDE(PetType.DOG, "Rawhide", "https://www.chewy.com/b/rawhide-1545", false, false),
    ANTLER(PetType.DOG, "Antlers", "https://www.chewy.com/b/antlers-1541", false, false),
    HIMA_CHEW(PetType.DOG, "Himalayan Chews", "https://www.chewy.com/b/himalayan-chews-2780", false, false),
    NATURAL_CHEW(PetType.DOG, "Natural Chews", "https://www.chewy.com/b/natural-chews-1544", false, false),
    RAWHIDE_ALT(PetType.DOG, "Rawhide Alternatives", "https://www.chewy.com/b/rawhide-alternatives-9939", false, false),
    HARD_CHEW(PetType.DOG, "Hard Chews", "https://www.chewy.com/b/hard-chews-9938", false, false),
    DOG_FOOD(PetType.DOG, "Food", "https://www.chewy.com/b/food-332", true, true),
    CAT_FOOD(PetType.CAT, "Food", "https://www.chewy.com/b/food-387", true, true);

    private final PetType type;
    private final String category;
    private final String url;
    private final boolean wantNutrition;
    private final boolean wantFeeding;

    ChewyUrl(PetType type, String category, String url, boolean wantNutrition, boolean wantFeeding) {
        this.type = type;
        this.category = category;
        this.url = url;
        this.wantNutrition = wantNutrition;
        this.wantFeeding = wantFeeding;
    }

    public PetType getType() {
        return type;
    }

    public String getCategory() {
        return category;
    }

    public String getUrl() {
        return url;
    }

    public boolean isWantNutrition() {
        return wantNutrition;
    }

    public boolean isWantFeeding() {
        return wantFeeding;
    }
}
