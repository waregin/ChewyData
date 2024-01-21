package com.marozilla.countdown;

import java.time.*;

public class TopSurgeryCountdown {
    public static void main(String[] args) {
        ZonedDateTime topSurgeryDateTime = ZonedDateTime.of(2021, 11, 3, 5, 30, 0, 0, ZoneOffset.systemDefault());
        ZonedDateTime now = ZonedDateTime.now();

        long topSurgeryEpoch = topSurgeryDateTime.toEpochSecond();
        long nowEpoch = now.toEpochSecond();
        long waitPeriodEpoch = topSurgeryEpoch - nowEpoch;

        long days = waitPeriodEpoch / 86400;
        long partialDaySeconds = waitPeriodEpoch % 86400;
        long hours = partialDaySeconds / 3600;
        partialDaySeconds = partialDaySeconds % 3600;
        long minutes = partialDaySeconds / 60;
        long seconds = partialDaySeconds % 60;

        System.out.println(days + " days " + hours + " hours " + minutes + " minutes " + seconds + " seconds remain before top surgery arrival time");
    }
}
