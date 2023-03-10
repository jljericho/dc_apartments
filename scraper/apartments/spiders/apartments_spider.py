import logging
from pathlib import Path
import time

import scrapy


class ApartmentsDotComSpider(scrapy.Spider):
    name = "apartments_dot_com"

    def start_requests(self):
        urls = [
            # 'https://www.apartments.com/washington-dc/',
            # 'https://www.apartments.com/arlington-va/',

            # 'https://www.apartments.com/alexandria-va/',
            "https://www.apartments.com/dupont-circle-washington-dc/",
            "https://www.apartments.com/cathedral-heights-washington-dc/",
            "https://www.apartments.com/logan-circle-washington-dc/",
            "https://www.apartments.com/capitol-hill-washington-dc/"
        ]
        for url in urls:
            yield scrapy.Request(url=url, callback=self.parse_search_page)

    def parse(self, response, **kwargs):
        pass

    ###
    # Search Page
    ###

    def parse_search_page(self, response):
        """
        @url https://www.apartments.com/condos/dupont-circle-washington-dc/
        @returns items 0
        @returns requests 1
        """
        for property_div in response.css("div.property-info"):
            unit_link = property_div.css("a.property-link::attr(href)")
            yield scrapy.Request(unit_link.get(), callback=self.parse_result_page)
        next_page_link = response.css("head link[rel='next']::attr(href)").get()
        print(next_page_link)
        if next_page_link:
            yield scrapy.Request(next_page_link, callback=self.parse_search_page)

    ###
    # Result Page
    ###

    def parse_result_page(self, response):
        property_info = self._extract_property_information(response)
        if not self._has_multiple_models(response):
            yield property_info
        else:
            yield from self._extract_models(response, property_info)

    @classmethod
    def _extract_property_information(cls, response) -> dict:
        info = dict()
        info["property_name"] = response.css("h1::text").get().strip(" \r\n")
        info["address"] = response.css("span.delivery-address").css("span::text").get() or info["property_name"]

        state_zip = response.css("span.stateZipContainer span::text").getall()
        info["state"] = response.css("span.stateZipContainer span::text").getall()[0]
        info["zip_code"] = state_zip[1] if len(state_zip) > 1 else None

        info.update({
            "price": response.xpath("//p[text()='Monthly Rent']/following-sibling::p[1]/text()").get(),
            "bedrooms": response.xpath("//p[text()='Bedrooms']/following-sibling::p[1]/text()").get(),
            "bathrooms": response.xpath("//p[text()='Bathrooms']/following-sibling::p[1]/text()").get(),
            "square_feet": response.xpath("//p[text()='Square Feet']/following-sibling::p[1]/text()").get(),
            "neighborhood": response.css("a.neighborhood::text").get(),
            "walk_score": response.css("div#walkScoreValue::text").get(),
            "transit_score": response.css("div.transitScore::attr(data-score)").get(),
            "bike_score": response.css("div.bikeScore::attr(data-score)").get(),
            "description": response.css("section.descriptionSection p::text").get(),
            "rating": response.css("div.averageRating::text").get(),
            "build_year": response.xpath("//div[contains(text(), 'Built in')]/text()").get()
        })
        info.update(cls._extract_property_fees(response))
        return info

    @classmethod
    def _extract_property_fees(cls, response) -> dict:
        fees = {
            "application_fee": response.xpath("//div[text()='Application Fee']/following-sibling::div[1]/text()").get(),
            "admin_fee": response.xpath("//div[text()='Admin Fee']/following-sibling::div[1]/text()").get()
        }
        parking_options = list()
        for fee_group in response.css("div.feespolicies"):
            if fee_group.css("h4::text").get() == "Parking":
                for parking_option in fee_group.css("li"):
                    parking_options.append({
                        "title": parking_option.css("div.column::text").get(),
                        "cost": parking_option.css("div.column-right::text").get(),
                        "description": parking_option.css("div.subTitle::text").get()
                    })
        fees["parking"] = parking_options
        return fees

    @classmethod
    def _has_multiple_models(cls, response) -> bool:
        return response.css("div.pricingGridItem").get()

    @classmethod
    def _extract_models(cls, response, property_info: dict):
        for model in response.css("div.pricingGridItem"):
            info = property_info.copy()
            model_stats = model.css("span.detailsTextWrapper span::text").getall()[:3]
            if len(model_stats) == 3:
                beds, bath, sqft_range = model_stats
            elif len(model_stats) == 2:
                beds, bath = model_stats
            else:
                beds, bath = None, None
            info.update({
                "model": model.css("span.modelName::text").get(),
                "bedrooms": beds,
                "bathrooms": bath
            })
            yield from cls._extract_units(model, model_info=info)

    @classmethod
    def _extract_units(cls, model, model_info: dict):
        for unit in model.css("li.unitContainer"):
            info = model_info.copy()
            info.update({
                "unit": "".join(unit.css("button.unitBtn *::text").getall()).strip(" \r\n"),
                "price": "".join(unit.css("div.pricingColumn span *::text").getall()).replace("price ", "").strip(" \r\n"),
                "square_feet": "".join(unit.css("div.sqftColumn span *::text").getall()).replace("square feet ", "").strip(" \r\n"),
                "available": "".join(unit.css("span.dateAvailable *::text").getall()).replace("availibility ", "").strip(" \r\n"),
            })
            yield info
