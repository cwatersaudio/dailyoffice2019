import csv
import os
from distutils.util import strtobool
from urllib.parse import quote

from bs4 import BeautifulSoup
from django.http import HttpResponse
from django.template.loader import render_to_string
from django.utils.functional import cached_property
from django.utils.safestring import mark_safe
from django.views.generic.base import TemplateResponseMixin
from rest_framework import serializers, mixins, viewsets
from rest_framework.generics import ListAPIView
from rest_framework.response import Response
from rest_framework.views import APIView

from churchcal.api.permissions import ReadOnly
from churchcal.api.serializer import DaySerializer
from office.api.serializers import UpdateNoticeSerializer
from office.api.views import Module, Line
from office.api.views.ep import EPOpeningSentence
from office.canticles import DefaultCanticles, BCP1979CanticleTable, REC2011CanticleTable
from office.models import (
    UpdateNotice,
    HolyDayOfficeDay,
    StandardOfficeDay,
    ThirtyDayPsalterDay,
    Setting,
    SettingOption,
)
from office.utils import passage_to_citation


class UpdateNoticeView(TemplateResponseMixin, ListAPIView):
    queryset = UpdateNotice.objects.all()
    serializer_class = UpdateNoticeSerializer

    # def get_queryset(self):
    #     queryset = UpdateNotice.objects.order_by("-version", "-created")
    #     mode = self.request.path.split('/').pop()
    #     if mode == 'web':
    #         queryset = queryset.filter(web_mode=True)
    #     if mode == 'app':
    #         queryset = queryset.filter(app_mode=True)
    #     return queryset.all()


class Settings(dict):
    DEFAULT_SETTINGS = {
        "psalter": "60",
        "reading_cycle": "1",
        "reading_length": "full",
        "reading_audio": "off",
        "canticle_rotation": "default",
        "theme": "theme-auto",
        "lectionary": "daily-office-readings",
        "confession": "long-on-fast",
        "absolution": "lay",
        "morning_prayer_invitatory": "invitatory_traditional",
        "reading_headings": "off",
        "language_style": "traditional",
        "national_holidays": "all",
        "suffrages": "rotating",
        "collects": "rotating",
        "pandemic_prayers": "pandemic_yes",
        "mp_great_litany": "mp_litany_off",
        "ep_great_litany": "ep_litany_off",
        "general_thanksgiving": "on",
        "chrysostom": "on",
        "grace": "rotating",
        "o_antiphons": "literal",
    }

    def __init__(self, request):
        settings = self._get_settings(request)
        super().__init__(**settings)

    def _get_settings(self, request):
        settings = self.DEFAULT_SETTINGS.copy()
        specified_settings = {k: v for (k, v) in request.query_params.items() if k in settings.keys()}
        for k, v in settings.items():
            if k in specified_settings.keys():
                settings[k] = specified_settings[k]
        return settings


# heading
# subheading
# citation
# html
# leader
# congregation
# rubric
# leader_dialogue
# congregation_dialogue


def file_to_lines(filename):
    def process_row(row):
        result = {"content": row[0]}
        if len(row) > 1 and row[1]:
            result["line_type"] = row[1]
        if len(row) > 2:
            if not row[2]:
                result["indented"] = False
            else:
                result["indented"] = bool(strtobool(row[2].lower()))
        if len(row) > 3:
            if not row[3]:
                result["extra_space_before"] = False
            else:
                result["extra_space_before"] = bool(strtobool(row[3].lower()))
        return result

    filename = "{}.csv".format(filename.replace(".csv", ""))
    dir_path = os.path.dirname(os.path.realpath(__file__))
    with open("{}/../texts/{}".format(dir_path, filename), encoding="utf-8") as csvfile:
        reader = csv.reader(csvfile, quotechar='"', delimiter=",", quoting=csv.QUOTE_ALL, skipinitialspace=True)
        return [Line(**process_row(row)) for row in reader]


class MPOpeningSentence(Module):
    name = "Opening Sentence"

    def get_sentence(self):

        if "Thanksgiving Day" in self.office.date.primary.name:
            return {
                "sentence": "Honor the Lord with your wealth and with the firstfruits of all your produce; then your barns will be filled with plenty, and your vats will be bursting with wine.",
                "citation": "PROVERBS 3:9-10",
            }

        if self.office.date.season.name == "Holy Week":
            return {
                "sentence": "Is it nothing to you, all you who pass by? Look and see if there is any sorrow like my sorrow, which was brought upon me, which the Lord inflicted on the day of his fierce anger.",
                "citation": "LAMENTATIONS 1:12",
            }

        if (
            self.office.date.season.name == "Lent"
            or self.office.date.primary.rank.name == "EMBER_DAY"
            or self.office.date.primary.rank.name == "ROGATION_DAY"
        ):

            if self.office.date.date.weekday() in [6, 2]:  # Sunday, Wednesday
                return {"sentence": "Repent, for the kingdom of heaven is at hand.", "citation": "MATTHEW 3:2"}

            if self.office.date.date.weekday() in [0, 3, 5]:  # Monday, Thursday, Saturday
                return {
                    "sentence": "Turn your face from my sins, and blot out all my misdeeds.",
                    "citation": "PSALM 51:9",
                }

            return {
                "sentence": "If anyone would come after me, let him deny himself and take up his cross and follow me.",
                "citation": "MARK 8:34",
            }

        if self.office.date.season.name == "Advent":
            return {
                "sentence": "In the wilderness prepare the way of the Lord; make straight in the desert a highway for our God.",
                "citation": "ISAIAH 40:3",
            }

        if self.office.date.season.name == "Christmastide":
            return {
                "sentence": "Fear not, for behold, I bring you good news of great joy that will be for all the people. For unto you is born this day in the city of David a Savior, who is Christ the Lord.",
                "citation": "LUKE 2:10-11",
            }

        if self.office.date.season.name == "Epiphanytide":
            return {
                "sentence": "From the rising of the sun to its setting my name will be great among the nations, and in every place incense will be offered to my name, and a pure offering. For my name will be great among the nations, says the Lord of hosts.",
                "citation": "MALACHI 1:11",
            }

        if (
            "Ascension" in self.office.date.primary.name
            or len(self.office.date.all) > 1
            and "Ascension" in self.office.date.all[1].name
        ):
            return {
                "sentence": "Since then we have a great high priest who has passed through the heavens, Jesus, the Son of God, let us hold fast our confession. Let us then with confidence draw near to the throne of grace, that we may receive mercy and find grace to help in time of need.",
                "citation": "HEBREWS 4:14, 16",
            }

        if self.office.date.primary.name == "The Day of Pentecost":
            return {
                "sentence": "You will receive power when the Holy Spirit has come upon you, and you will be my witnesses in Jerusalem and in all Judea and Samaria, and to the end of the earth.",
                "citation": "ACTS 1:8",
            }

        if self.office.date.primary.name == "Trinity Sunday":
            return {
                "sentence": "Holy, holy, holy, is the Lord God Almighty, who was and is and is to come!",
                "citation": "REVELATION 4:8",
            }

        if self.office.date.season.name == "Eastertide":
            return {
                "sentence": "If then you have been raised with Christ, seek the things that are above, where Christ is, seated at the right hand of God.",
                "citation": "COLOSSIANS 3:1",
            }

        if self.office.date.date.weekday() == 6:
            return {
                "sentence": "Grace to you and peace from God our Father and the Lord Jesus Christ.",
                "citation": "PHILIPPIANS 1:2",
            }

        if self.office.date.date.weekday() == 0:
            return {
                "sentence": "I was glad when they said unto me, “We will go into the house of the Lord.”",
                "citation": "PSALM 122:1",
            }

        if self.office.date.date.weekday() == 1:
            return {
                "sentence": "Let the words of my mouth and the meditation of my heart be always acceptable in your sight, O Lord, my rock and my redeemer.",
                "citation": "PSALM 19:14",
            }

        if self.office.date.date.weekday() == 2:
            return {
                "sentence": "The Lord is in his holy temple; let all the earth keep silence before him.",
                "citation": "HABAKKUK 2:20",
            }

        if self.office.date.date.weekday() == 3:
            return {
                "sentence": "O send out your light and your truth, that they may lead me, and bring me to your holy hill, and to your dwelling.",
                "citation": "PSALM 43:3",
            }

        if self.office.date.date.weekday() == 4:
            return {
                "sentence": "Thus says the One who is high and lifted up, who inhabits eternity, whose name is Holy: “I dwell in the high and holy place, and also with him who is of a contrite and lowly spirit, to revive the spirit of the lowly, and to revive the heart of the contrite.”",
                "citation": "ISAIAH 57:15",
            }

        if self.office.date.date.weekday() == 5:
            return {
                "sentence": "The hour is coming, and is now here, when the true worshipers will worship the Father in spirit and truth, for the Father is seeking such people to worship him.",
                "citation": "JOHN 4:23",
            }

    def get_lines(self):
        sentence = self.get_sentence()
        return [
            Line("Opening Sentence", "heading"),
            Line(sentence["sentence"], "leader"),
            Line(sentence["citation"], "citation"),
        ]


class Office(object):
    def __init__(self, request, year, month, day):
        from churchcal.calculations import get_calendar_date

        self.settings = Settings(request)

        self.date = get_calendar_date("{}-{}-{}".format(year, month, day))

        try:
            self.office_readings = HolyDayOfficeDay.objects.get(commemoration=self.date.primary)
        except HolyDayOfficeDay.DoesNotExist:
            self.office_readings = StandardOfficeDay.objects.get(month=self.date.date.month, day=self.date.date.day)

        self.thirty_day_psalter_day = ThirtyDayPsalterDay.objects.get(day=self.date.date.day)

    def get_modules(self):
        raise NotImplementedError("You must implement this method.")


class Confession(Module):
    name = "Confession of Sin"

    def get_intro_lines(self):
        setting = self.office.settings["confession"]
        fast = self.office.date.fast_day
        long = (setting == "long") or (setting == "long-on-fast" and fast)
        if long:
            return file_to_lines("confession_intro_long")
        return file_to_lines("confession_intro_short")

    def get_body_lines(self):
        return file_to_lines("confession_body")

    def get_absolution_lines(self):
        lay = self.office.settings["absolution"] == "lay"
        if lay:
            return file_to_lines("confession_absolution_lay")
        setting = self.office.settings["confession"]
        fast = self.office.date.fast_day
        long = (setting == "long") or (setting == "long-on-fast" and fast)
        if long:
            return file_to_lines("confession_absolution_long")
        return file_to_lines("confession_absolution_short")

    def get_lines(self):
        return (
            [Line("Confession of Sin", "heading")]
            + [Line("The Officiant says to the People", "rubric")]
            + self.get_intro_lines()
            + self.get_body_lines()
            + self.get_absolution_lines()
        )


class Preces(Module):
    name = "Preces"

    def get_lines(self):
        return file_to_lines("preces")


class MPInvitatory(Module):
    name = "Invitatory"

    @cached_property
    def antiphon(self):

        if "Presentation" in self.office.date.primary.name or "Annunciation" in self.office.date.primary.name:
            return {
                "first_line": "The Word was made flesh and dwelt among us:",
                "second_line": "O come, let us adore him.",
            }

        if self.office.date.primary.name == "The Day of Pentecost":
            return {
                "first_line": "Alleluia. The Spirit of the Lord renews the face of the earth:",
                "second_line": "O come, let us adore him.",
            }

        if self.office.date.primary.name == "Trinity Sunday":
            return {"first_line": "Father, Son, and Holy Spirit, one God:", "second_line": "O come, let us adore him."}

        if self.office.date.primary.name == "Easter Day":
            return {"first_line": "Alleluia. The Lord is risen indeed:", "second_line": "O come, let us adore him."}

        if (
            "Ascension" in self.office.date.primary.name
            or len(self.office.date.all) > 1
            and "Ascension" in self.office.date.all[1].name
        ):
            return {
                "first_line": "Alleluia. Christ the Lord has ascended into heaven:",
                "second_line": "O come, let us adore him.",
            }

        if self.office.date.primary.name == "The Transfiguration of Our Lord Jesus Christ":
            return {"first_line": "The Lord has shown forth his glory:", "second_line": "O come, let us adore him."}

        if self.office.date.primary.name == "All Saints’ Day":
            return {"first_line": "The Lord is glorious in his saints:", "second_line": "O come, let us adore him."}

        if self.office.date.primary.rank.name == "HOLY_DAY" and self.office.date.primary.name not in (
            "The Circumcision and Holy Name of our Lord Jesus Christ",
            "The Visitation of the Virgin Mary to Elizabeth and Zechariah",
            "Holy Cross Day",
            "The Holy Innocents",
        ):
            return {"first_line": "The Lord is glorious in his saints:", "second_line": "O come, let us adore him."}

        if self.office.date.season.name == "Lent" or self.office.date.season.name == "Holy Week":
            return {
                "first_line": "The Lord is full of compassion and mercy:",
                "second_line": "O come, let us adore him.",
            }

        if self.office.date.season.name == "Advent":
            return {"first_line": "Our King and Savior now draws near:", "second_line": "O come, let us adore him."}

        if self.office.date.season.name == "Christmastide":
            return {"first_line": "Alleluia, to us a child is born:", "second_line": "O come, let us adore him."}

        if self.office.date.season.name == "Epiphanytide":
            return {"first_line": "The Lord has shown forth his glory:", "second_line": "O come, let us adore him."}

        if self.office.date.season.name == "Eastertide":
            for commemoration in self.office.date.all:
                if "Ascension Day" in commemoration.name:
                    return {
                        "first_line": "Alleluia. Christ the Lord has ascended into heaven:",
                        "second_line": "O come, let us adore him.",
                    }

            return {"first_line": "Alleluia. The Lord is risen indeed:", "second_line": "O come, let us adore him."}

        if self.office.date.date.weekday() in [0, 3, 6]:
            return {
                "first_line": "The earth is the Lord’s for he made it: ",
                "second_line": "O come, let us adore him.",
            }

        if self.office.date.date.weekday() in [1, 4]:
            return {
                "first_line": "Worship the Lord in the beauty of holiness:",
                "second_line": "O come, let us adore him.",
            }

        if self.office.date.date.weekday() in [2, 5]:
            return {"first_line": "The mercy of the Lord is everlasting: ", "second_line": "O come, let us adore him."}

    def rotating(self):
        if "Easter Day" in self.office.date.primary.name or "Easter Week" in self.office.date.primary.name:
            return ("pascha_nostrum", "pascha_nostrum")

        if self.office.date.season.name == "Eastertide":
            if self.office.date.date.timetuple().tm_yday % 3 == 0:
                return ("pascha_nostrum", "pascha_nostrum")

        if self.office.date.date.timetuple().tm_yday % 2 == 0:
            thirty_day = "jubilate"
            sixty_day = "jubilate"
            if "100" in self.office.office_readings.mp_psalms.split(","):
                sixty_day = "venite"

            if "100" in self.office.thirty_day_psalter_day.mp_psalms.split(","):
                thirty_day = "venite"
        else:
            thirty_day = "venite"
            sixty_day = "venite"
            if "95" in self.office.office_readings.mp_psalms.split(","):
                sixty_day = "jubilate"

            if "95" in self.office.thirty_day_psalter_day.mp_psalms.split(","):
                thirty_day = "jubilate"

        return (thirty_day, sixty_day)

    def venite_most_days(self):
        if "Easter Day" in self.office.date.primary.name or "Easter Week" in self.office.date.primary.name:
            return ("pascha_nostrum", "pascha_nostrum")

        thirty_day = "venite"
        sixty_day = "venite"

        if "95" in self.office.office_readings.mp_psalms.split(","):
            sixty_day = "jubilate"

        if "95" in self.office.thirty_day_psalter_day.mp_psalms.split(","):
            thirty_day = "jubilate"

        return (thirty_day, sixty_day)

    def jubilate_on_sundays_and_feasts(self):
        if "Easter Day" in self.office.date.primary.name or "Easter Week" in self.office.date.primary.name:
            return ("pascha_nostrum", "pascha_nostrum")

        if self.office.date.season.name == "Eastertide" and self.office.date.primary.rank.name in (
            "PRINCIPAL_FEAST",
            "SUNDAY",
            "HOLY_DAY",
        ):
            return ("pascha_nostrum", "pascha_nostrum")

        if self.office.date.primary.rank.name in ("PRINCIPAL_FEAST", "SUNDAY", "HOLY_DAY"):
            thirty_day = "jubilate"
            sixty_day = "jubilate"

            if "100" in self.office.office_readings.mp_psalms.split(","):
                sixty_day = "venite"
            if "100" in self.office.thirty_day_psalter_day.mp_psalms.split(","):
                thirty_day = "venite"
            return (thirty_day, sixty_day)

        thirty_day = "venite"
        sixty_day = "venite"

        if "95" in self.office.office_readings.mp_psalms.split(","):
            sixty_day = "jubilate"

        if "95" in self.office.thirty_day_psalter_day.mp_psalms.split(","):
            thirty_day = "jubilate"

        return (thirty_day, sixty_day)

    def celebratory_always(self):

        if self.office.date.season.name == "Eastertide":
            return ("pascha_nostrum", "pascha_nostrum")

        thirty_day = "jubilate"
        sixty_day = "jubilate"

        if "100" in self.office.office_readings.mp_psalms.split(","):
            sixty_day = "venite"
        if "100" in self.office.thirty_day_psalter_day.mp_psalms.split(","):
            thirty_day = "venite"
        return (thirty_day, sixty_day)

    def get_canticle_filename(self):
        setting = self.office.settings["morning_prayer_invitatory"]
        canticles = self.venite_most_days()
        if setting == "invitatory_jubilate_on_feasts":
            canticles = self.jubilate_on_sundays_and_feasts()
        if setting == "invitatory_rotating":
            canticles = self.rotating()
        if setting == "celebratory_always":
            canticles = self.celebratory_always()

        canticle = canticles[1]
        if self.office.settings["psalter"] == "30":
            canticle = canticles[0]

        lent = self.office.date.season.name == "Lent" or self.office.date.season.name == "Holy Week"
        if canticle == "venite" and lent:
            canticle = "venite_lent"

        return canticle

    def get_lines(self):

        filename = self.get_canticle_filename()
        if filename != "pascha_nostrum":
            canticle = file_to_lines(filename)
            canticle_heading = canticle[:2]
            canticle_body = canticle[2:]
            return (
                canticle_heading
                + [Line(self.antiphon["first_line"], "leader"), Line(self.antiphon["second_line"])]
                + canticle_body
                + [Line(self.antiphon["first_line"], "leader"), Line(self.antiphon["second_line"])]
            )
        return file_to_lines(filename)


class EPInvitatory(Module):
    def get_lines(self):
        return file_to_lines("phos_hilaron.csv")


class MPPsalms(Module):
    name = "Psalms"
    attribute = "mp_psalms"

    @staticmethod
    def heading(citations):
        return "The Psalm{} Appointed".format("s" if len(citations) > 1 else "")

    def mass(self):
        pass

    def thirty_days(self):
        from psalter.utils import get_psalms

        psalms = getattr(self.office.thirty_day_psalter_day, self.attribute)
        citations = psalms.split(",")
        heading = self.heading(citations)
        psalms = get_psalms(psalms, api=True)

        return [Line(heading, "heading"), Line("Thirty Day Cycle", "subheading")] + psalms

    def sixty_days(self):
        from psalter.utils import get_psalms

        psalms = getattr(self.office.office_readings.mp_psalms, self.attribute)
        psalms = psalms.split("or")

        if len(psalms) > 1:
            if (self.office.date.date.year % 2) == 0:
                psalms = psalms[0]
            else:
                psalms = psalms[1]
        else:
            psalms = psalms[0]

        citations = psalms.split(",")
        heading = self.heading(citations)
        psalms = get_psalms(psalms, api=True)

        return [Line(heading, "heading"), Line("Sixty Day Cycle", "subheading")] + psalms

    def mass_psalms(self):
        from psalter.utils import get_psalms

        mass_psalm = None
        for reading in self.office.date.mass_readings:
            if reading.reading_type == "psalm":
                mass_psalm = reading.long_citation.replace("Psalms", "").replace("Psalm", "").strip()
                break
        if not mass_psalm:
            return None

        heading = self.heading(mass_psalm)
        psalms = get_psalms(mass_psalm, api=True)
        return [Line(heading, "heading"), Line("Sunday & Holy Day Psalms", "subheading")] + psalms

    def get_psalm_lines(self):
        setting = self.office.settings["psalter"]
        lectionary = self.office.settings["lectionary"]
        if lectionary == "mass-readings":
            mass_psalms = self.mass_psalms()
            if mass_psalms:
                return mass_psalms

        if setting == "60":
            return self.sixty_days()
        return self.thirty_days()

    def gloria_patri(self):
        return [Line("", "spacer")] + file_to_lines("gloria_patri")

    def get_lines(self):
        return self.get_psalm_lines() + self.gloria_patri()


class EPPsalms(MPPsalms):
    attribute = "ep_psalms"


class ReadingModule(Module):
    def remove_headings_if_needed(self, text):
        reading_headings = self.office.settings["reading_headings"] == "on"
        if reading_headings:
            return text

        soup = BeautifulSoup(text, "html.parser")
        for h3 in soup.find_all("h3", {"class": "reading-heading"}):
            h3.decompose()
        return str(soup)

    def audio(self, passage, testament):
        if testament == "DC":
            return None
        reading_audio = self.office.settings["reading_audio"] == "on"
        if not reading_audio:
            return None
        passage = quote(passage)
        return '<iframe src="https://www.esv.org/audio-player/{}" style="border: 0; width: 100%; height: 109px;"></iframe>'.format(
            passage
        )

    @staticmethod
    def closing(testament):
        return "The Word of the Lord." if testament != "DC" else "Here ends the Reading."

    @staticmethod
    def closing_response(testament):
        return "Thanks be to God." if testament != "DC" else None

    @cached_property
    def has_mass_reading(self):
        return self.office.date.primary.rank.precedence_rank <= 4

    def get_mass_reading_lines(self, reading):
        text = self.remove_headings_if_needed(reading.long_text)
        lines = [
            Line(reading.long_citation, "subheading"),
            Line(self.audio(reading.long_citation, reading.testament), "html"),
            Line(passage_to_citation(reading.long_citation), "leader"),
            Line(text, "html", "html"),
            Line(self.closing(reading.testament), "leader"),
            Line(self.closing_response(reading.testament), "congregation"),
        ]
        return [line for line in lines if line and line["content"]]

    def get_reading(self, field, abbreviated=False):

        subheading = getattr(self.office.office_readings, field)
        passage = getattr(self.office.office_readings, field)
        citation = passage_to_citation(getattr(self.office.office_readings, field))
        text = getattr(self.office.office_readings, "{}_text".format(field))
        closing = self.closing(getattr(self.office.office_readings, "{}_testament".format(field)))
        closing_response = self.closing_response(getattr(self.office.office_readings, "{}_testament".format(field)))
        testament = getattr(self.office.office_readings, "{}_testament".format(field))

        if abbreviated:
            has_abbreviated = (
                True
                if hasattr(self.office.office_readings, "{}_abbreviated".format(field))
                and getattr(self.office.office_readings, "{}_abbreviated".format(field))
                else False
            )
            if has_abbreviated:
                subheading = getattr(self.office.office_readings, "{}_abbreviated".format(field))
                passage = getattr(self.office.office_readings, "{}_abbreviated".format(field))
                citation = passage_to_citation(getattr(self.office.office_readings, "{}_abbreviated".format(field)))
                text = getattr(self.office.office_readings, "{}_abbreviated_text".format(field))

        text = self.remove_headings_if_needed(text)

        lines = [
            Line(subheading, "subheading"),
            Line(self.audio(passage, testament), "html"),
            Line(citation, "leader"),
            Line("", "spacer"),
            Line(text, "html", "leader"),
            Line("", "spacer"),
            Line(closing, "leader"),
            Line(closing_response, "congregation"),
        ]
        return [line for line in lines if line and (line["content"] or line["line_type"] == "spacer")]

    def get_mass_reading(self, number):
        if not self.has_mass_reading:
            return []
        number = number + 1 if number > 1 else number
        for reading in self.office.date.mass_readings:
            if reading.reading_number == number:
                return self.get_mass_reading_lines(reading)
        return []

    def abbreviated_mass_reading(self, number):
        if not self.has_mass_reading:
            return []

        for reading in self.office.date.mass_readings:
            if reading.reading_number == number:
                if not reading.short_citation:
                    return self.get_mass_reading(number)
                return self.get_mass_reading_lines(reading)
        return []

    def get_lines_for_reading(self, office="mp", number=1):
        reading_cycle = self.office.settings["reading_cycle"]
        reading_length = self.office.settings["reading_length"]
        lectionary = self.office.settings["lectionary"]

        if lectionary == "mass-readings" and self.has_mass_reading:
            return (
                self.get_abbreviated_mass_reading(number)
                if reading_length == "abbreviated"
                else self.get_mass_reading(number)
            )

        if number > 2:
            return None

        abbreviated = reading_length == "abbreviated"
        if int(reading_cycle) == 2:
            has_alternate_reading = self.office.date.date.year % 2 == 0
            if has_alternate_reading:
                alternate_reading_field = "{}_reading_{}".format("ep" if office == "mp" else office, number)
                print(alternate_reading_field)
                return self.get_reading(alternate_reading_field, abbreviated)

        reading_field = "{}_reading_{}".format(office, number)
        return self.get_reading(reading_field, abbreviated)


class MPFirstReading(ReadingModule):
    name = "First Reading"

    def get_lines(self):
        reading_heading = [Line("The First Lesson", line_type="heading")]
        return reading_heading + self.get_lines_for_reading("mp", 1)


class EPFirstReading(ReadingModule):
    name = "First Reading"

    def get_lines(self):
        reading_heading = [Line("The First Lesson", line_type="heading")]
        return reading_heading + self.get_lines_for_reading("ep", 1)


class CanticleModule(Module):
    def rubric(self):
        return Line("The following Canticle is sung or said, all standing", line_type="rubric")

    def gloria_lines(self, data):
        if not data.gloria:
            return []
        return [
            Line(
                "Glory be to the Father, and to the Son, and to the Holy Spirit; *",
                line_type="congregation",
                indented=False,
            ),
            Line("as it was in the beginning, is now, and ever shall be,", line_type="congregation", indented=True),
            Line("world without end. Amen.", line_type="congregation", indented=True),
        ]

    def get_canticle(self, data):
        return (
            [
                Line(data.latin_name, "heading"),
                Line(data.english_name, "subheading"),
                self.rubric(),
            ]
            + file_to_lines(data.template.replace("html", "csv"))
            + [
                Line(data.citation, "citation"),
            ]
            + self.gloria_lines(data)
        )


class MPFirstCanticle(CanticleModule):
    name = "First Canticle"

    def get_lines(self):

        rotation = self.office.settings["canticle_rotation"]

        if rotation == "1979":
            data = BCP1979CanticleTable().get_mp_canticle_1(self.office.date)
        elif rotation == "2011":
            data = REC2011CanticleTable().get_mp_canticle_1(self.office.date)
        else:
            data = DefaultCanticles().get_mp_canticle_1(self.office.date)
        return self.get_canticle(data)


class EPFirstCanticle(CanticleModule):
    name = "First Canticle"

    def get_lines(self):

        rotation = self.office.settings["canticle_rotation"]

        if rotation == "1979":
            data = BCP1979CanticleTable().get_ep_canticle_1(self.office.date)
        elif rotation == "2011":
            data = REC2011CanticleTable().get_ep_canticle_1(self.office.date)
        else:
            data = DefaultCanticles().get_ep_canticle_1(self.office.date)
        return self.get_canticle(data)


class MPSecondCanticle(CanticleModule):
    name = "Second Canticle"

    def get_lines(self):

        rotation = self.office.settings["canticle_rotation"]

        if rotation == "1979":
            data = BCP1979CanticleTable().get_mp_canticle_2(self.office.date)
        elif rotation == "2011":
            data = REC2011CanticleTable().get_mp_canticle_2(self.office.date)
        else:
            data = DefaultCanticles().get_mp_canticle_2(self.office.date)
        return self.get_canticle(data)


class EPSecondCanticle(CanticleModule):
    name = "Second Canticle"

    def get_lines(self):

        rotation = self.office.settings["canticle_rotation"]

        if rotation == "1979":
            data = BCP1979CanticleTable().get_ep_canticle_2(self.office.date)
        elif rotation == "2011":
            data = REC2011CanticleTable().get_ep_canticle_2(self.office.date, self.office.office_readings)
        else:
            data = DefaultCanticles().get_ep_canticle_2(self.office.date)
        return self.get_canticle(data)


class MPSecondReading(ReadingModule):
    name = "Second Reading"

    def get_lines(self):
        reading_heading = [Line("The Second Lesson", line_type="heading")]
        return reading_heading + self.get_lines_for_reading("mp", 2)


class EPSecondReading(ReadingModule):
    name = "Second Reading"

    def get_lines(self):
        reading_heading = [Line("The Second Lesson", line_type="heading")]
        return reading_heading + self.get_lines_for_reading("ep", 2)


class MPThirdReading(ReadingModule):
    name = "Third Reading"

    def get_lines(self):
        if not self.has_mass_reading:
            return None

        reading_heading = [Line("The Third Lesson", line_type="heading")]
        lines = self.get_lines_for_reading("mp", 3)
        if lines:
            return reading_heading + lines
        return None


class EPThirdReading(ReadingModule):
    name = "Third Reading"

    def get_lines(self):
        if not self.has_mass_reading:
            return None

        reading_heading = [Line("The Third Lesson", line_type="heading")]
        lines = self.get_lines_for_reading("ep", 3)
        if lines:
            return reading_heading + lines
        return None


class Creed(Module):
    name = "The Apostle's Creed"

    def get_lines(self):
        return [
            Line("The Apostles' Creed", "heading"),
            Line("Officiant and People together, all standing", "rubric"),
        ] + file_to_lines("creed.csv")


class Prayers(Module):
    name = "The Prayers"

    def get_lines(self):
        style = self.office.settings["language_style"]
        if style == "contemporary":
            kryie_file = "kyrie_contemporary.csv"
            pater_file = "pater_contemporary.csv"
        else:
            kryie_file = "kyrie_traditional.csv"
            pater_file = "pater_traditional.csv"

        return (
            [
                Line("The Prayers", "heading"),
                Line("The Lord be with you.", "leader_dialogue", preface="Officiant"),
                Line("And with your spirit.", "people_dialogue", preface="People"),
                Line("Let us pray.", "leader_dialogue", preface="Officiant"),
                Line("The People kneel or stand.", "rubric"),
            ]
            + file_to_lines(kryie_file)
            + [Line("Officiant and People", "rubric")]
            + file_to_lines(pater_file)
            + file_to_lines("suffrages_a.csv")
        )


class MPCollectOfTheDay(Module):
    name = "Collect(s) of the Day"
    attribute = "morning_prayer_collect"
    commemoration_attribute = "all"

    def get_lines(self):
        collects = [
            [
                Line("Collect of the Day", "heading"),
                Line(commemoration.name, "subheading"),
                Line(getattr(commemoration, self.attribute).replace(" Amen.", ""), "leader"),
                Line("Amen.", "congregation"),
            ]
            for commemoration in getattr(self.office.date, self.commemoration_attribute)
            if getattr(commemoration, self.attribute)
        ]
        lines = [line for collect in collects for line in collect]
        return lines


class EPCollectOfTheDay(MPCollectOfTheDay):
    attribute = "evening_prayer_collect"
    commemoration_attribute = "all_evening"


class AdditionalCollects(Module):
    name = "Additional Collects"

    def get_weekly_collect(self):

        collect = self.weekly_collects[self.office.date.date.weekday()]
        return [
            Line(collect[0], "heading"),
            Line(collect[1], "subheading"),
            Line(collect[2], "leader"),
            Line("Amen.", "congregation"),
        ]

    def get_fixed_collect(self):

        lines = []
        for collect in self.fixed_collects:
            lines.append(Line(collect[0], "heading"))
            lines.append(Line(collect[1], "leader"))
            lines.append(Line("Amen.", "congregation"))

        return lines

    def get_lines(self):
        collect_rotation = self.office.settings["collects"]
        if collect_rotation == "fixed":
            return self.get_fixed_collect()
        return self.get_weekly_collect()


class MPAdditionalCollects(AdditionalCollects):
    fixed_collects = (
        (
            "A COLLECT FOR PEACE",
            "O God, the author of peace and lover of concord, to know you is eternal life and to serve you is perfect freedom: Defend us, your humble servants, in all assaults of our enemies; that we, surely trusting in your defense, may not fear the power of any adversaries, through the might of Jesus Christ our Lord.",
        ),
        (
            "A COLLECT FOR GRACE",
            "O Lord, our heavenly Father, almighty and everlasting God, you have brought us safely to the beginning of this day: Defend us by your mighty power, that we may not fall into sin nor run into any danger; and that, guided by your Spirit, we may do what is righteous in your sight; through Jesus Christ our Lord.",
        ),
    )

    weekly_collects = (
        (
            "A COLLECT FOR THE RENEWAL OF LIFE",
            "Monday",
            "O God, the King eternal, whose light divides the day from the night and turns the shadow of death into the morning: Drive far from us all wrong desires, incline our hearts to keep your law, and guide our feet into the way of peace; that, having done your will with cheerfulness during the day, we may, when night comes, rejoice to give you thanks; through Jesus Christ our Lord.",
        ),
        (
            "A COLLECT FOR PEACE",
            "Tuesday",
            "O God, the author of peace and lover of concord, to know you is eternal life and to serve you is perfect freedom: Defend us, your humble servants, in all assaults of our enemies; that we, surely trusting in your defense, may not fear the power of any adversaries, through the might of Jesus Christ our Lord.",
        ),
        (
            "A COLLECT FOR GRACE",
            "Wednesday",
            "O Lord, our heavenly Father, almighty and everlasting God, you have brought us safely to the beginning of this day: Defend us by your mighty power, that we may not fall into sin nor run into any danger; and that, guided by your Spirit, we may do what is righteous in your sight; through Jesus Christ our Lord.",
        ),
        (
            "A COLLECT FOR GUIDANCE",
            "Thursday",
            "Heavenly Father, in you we live and move and have our being: We humbly pray you so to guide and govern us by your Holy Spirit, that in all the cares and occupations of our life we may not forget you, but may remember that we are ever walking in your sight; through Jesus Christ our Lord.",
        ),
        (
            "A COLLECT FOR ENDURANCE ",
            "Friday",
            "Almighty God, whose most dear Son went not up to joy but first he suffered pain, and entered not into glory before he was crucified: Mercifully grant that we, walking in the way of the Cross, may find it none other than the way of life and peace; through Jesus Christ your Son our Lord.",
        ),
        (
            "A COLLECT FOR SABBATH REST",
            "Saturday",
            "Almighty God, who after the creation of the world rested from all your works and sanctified a day of rest for all your creatures: Grant that we, putting away all earthly anxieties, may be duly prepared for the service of your sanctuary, and that our rest here upon earth may be a preparation for the eternal rest promised to your people in heaven; through Jesus Christ our Lord.",
        ),
        (
            "A COLLECT FOR STRENGTH TO AWAIT CHRIST’S RETURN",
            "Sunday",
            "O God our King, by the resurrection of your Son Jesus Christ on the first day of the week, you conquered sin, put death to flight, and gave us the hope of everlasting life: Redeem all our days by this victory; forgive our sins, banish our fears, make us bold to praise you and to do your will; and steel us to wait for the consummation of your kingdom on the last great Day; through Jesus Christ our Lord.",
        ),
    )


class EPAdditionalCollects(AdditionalCollects):
    weekly_collects = (
        (
            "A COLLECT FOR PEACE",
            "Monday",
            "O God, the source of all holy desires, all good counsels, and all just works: Give to your servants that peace which the world cannot give, that our hearts may be set to obey your commandments, and that we, being defended from the fear of our enemies, may pass our time in rest and quietness; through the merits of Jesus Christ our Savior.",
        ),
        (
            "A COLLECT FOR AID AGAINST PERILS",
            "Tuesday",
            "Lighten our darkness, we beseech you, O Lord; and by your great mercy defend us from all perils and dangers of this night; for the love of your only Son, our Savior Jesus Christ.",
        ),
        (
            "A COLLECT FOR PROTECTION",
            "Wednesday",
            "O God, the life of all who live, the light of the faithful, the strength of those who labor, and the repose of the dead: We thank you for the blessings of the day that is past, and humbly ask for your protection through the coming night. Bring us in safety to the morning hours; through him who died and rose again for us, your Son our Savior Jesus Christ.",
        ),
        (
            "A COLLECT FOR THE PRESENCE OF CHRIST",
            "Thursday",
            "Lord Jesus, stay with us, for evening is at hand and the day is past; be our companion in the way, kindle our hearts, and awaken hope, that we may know you as you are revealed in Scripture and the breaking of bread. Grant this for the sake of your love.",
        ),
        (
            "A COLLECT FOR FAITH",
            "Friday",
            "Lord Jesus Christ, by your death you took away the sting of death: Grant to us your servants so to follow in faith where you have led the way, that we may at length fall asleep peacefully in you and wake up in your likeness; for your tender mercies’ sake.",
        ),
        (
            "A COLLECT FOR THE EVE OF WORSHIP",
            "Saturday",
            "O God, the source of eternal light: Shed forth your unending day upon us who watch for you, that our lips may praise you, our lives may bless you, and our worship on the morrow give you glory; through Jesus Christ our Lord.",
        ),
        (
            "A COLLECT FOR RESURRECTION HOPE",
            "Sunday",
            "Lord God, whose Son our Savior Jesus Christ triumphed over the powers of death and prepared for us our place in the new Jerusalem: Grant that we, who have this day given thanks for his resurrection, may praise you in that City of which he is the light, and where he lives and reigns for ever and ever.",
        ),
    )

    fixed_collects = (
        (
            "A COLLECT FOR PEACE",
            "O God, the source of all holy desires, all good counsels, and all just works: Give to your servants that peace which the world cannot give, that our hearts may be set to obey your commandments, and that we, being defended from the fear of our enemies, may pass our time in rest and quietness; through the merits of Jesus Christ our Savior.",
        ),
        (
            "A COLLECT FOR AID AGAINST PERILS",
            "Lighten our darkness, we beseech you, O Lord; and by your great mercy defend us from all perils and dangers of this night; for the love of your only Son, our Savior Jesus Christ.",
        ),
    )


class ShowGreatLitanyMixin(object):
    @property
    def show_great_litany(self):
        if self.office_name == "evening_prayer":
            setting = self.office.settings["ep_great_litany"]
        else:
            setting = self.office.settings["mp_great_litany"]
        if setting in ["mp_litany_off", "ep_litany_off"]:
            return False
        if setting in ["mp_litany_everyday", "ep_litany_everyday"]:
            return True
        if setting in ["mp_litany_w_f_s", "ep_litany_w_f_s"]:
            return self.office.date.date.weekday() in [2, 4, 6]
        return False


class MissionCollect(ShowGreatLitanyMixin, Module):
    name = "Collect for Mission"

    def get_lines(self):

        if self.show_great_litany:
            return None

        day_of_year = self.office.date.date.timetuple().tm_yday
        collect_number = day_of_year % 3

        if collect_number == 0:
            collect = self.mission_collects[0]
            number = "I"
        elif collect_number == 1:
            collect = self.mission_collects[1]
            number = "II"
        else:
            collect = self.mission_collects[2]
            number = "III"

        return [
            Line("A Collect for Mission ({})".format(number), "heading"),
            Line(collect, "leader"),
            Line("Amen.", "congregation"),
        ]


class MPMissionCollect(MissionCollect):
    office_name = "morning_prayer"

    mission_collects = (
        "Almighty and everlasting God, who alone works great marvels: Send down upon our clergy and the congregations committed to their charge the life-giving Spirit of your grace, shower them with the continual dew of your blessing, and ignite in them a zealous love of your Gospel; through Jesus Christ our Lord. ",
        "O God, you have made of one blood all the peoples of the earth, and sent your blessed Son to preach peace to those who are far off and to those who are near: Grant that people everywhere may seek after you and find you; bring the nations into your fold; pour out your Spirit upon all flesh; and hasten the coming of your kingdom; through Jesus Christ our Lord.",
        "Lord Jesus Christ, you stretched out your arms of love on the hard wood of the Cross that everyone might come within the reach of your saving embrace: So clothe us in your Spirit that we, reaching forth our hands in love, may bring those who do not know you to the knowledge and love of you; for the honor of your Name.",
    )


class EPMissionCollect(MissionCollect):
    office_name = "evening_prayer"

    mission_collects = (
        "O God and Father of all, whom the whole heavens adore: Let the whole earth also worship you, all nations obey you, all tongues confess and bless you, and men, women, and children everywhere love you and serve you in peace; through Jesus Christ our Lord.",
        "Keep watch, dear Lord, with those who work, or watch, or weep this night, and give your angels charge over those who sleep. Tend the sick, Lord Christ; give rest to the weary, bless the dying, soothe the suffering, pity the afflicted, shield the joyous; and all for your love’s sake.",
        "O God, you manifest in your servants the signs of your presence: Send forth upon us the Spirit of love, that in companionship with one another your abounding grace may increase among us; through Jesus Christ our Lord.",
    )


class Intercessions(Module):
    name = "Intercessions, Thanksgivings, and Praise"

    def get_lines(self):
        return [
            Line("Intercessions, Thanksgivings, and Praise", "heading"),
            Line("The Officiant may invite the People to offer intercessions and thanksgivings.", "rubric"),
            Line("A hymn or anthem may be sung.", "rubric"),
        ]


class FinalPrayers(Module):
    name = "Final Prayers"

    def get_lines(self):
        general_thanksgiving = self.office.settings["general_thanksgiving"]
        chrysostom = self.office.settings["chrysostom"]

        lines = []

        if general_thanksgiving == "on":
            lines = (
                lines
                + [
                    Line("The General Thanksgiving", "heading"),
                    Line("Officiant and People", "rubric"),
                ]
                + file_to_lines("general_thanksgiving")
            )

        if chrysostom == "on":
            lines = (
                lines
                + [
                    Line("A Prayer of St. John Chrysostom", "heading"),
                ]
                + file_to_lines("chrysostom")
            )

        return lines


class Dismissal(Module):
    name = "Dismissal"

    def get_fixed_grace(self):

        return {
            "officiant": "The grace of our Lord Jesus Christ, and the love of God, and the fellowship of the Holy Spirit, be with us all evermore.",
            "people": "Amen.",
            "citation": "2 CORINTHIANS 13:14",
        }

    def get_grace(self):

        if self.office.date.date.weekday() in (6, 2, 5):
            return {
                "officiant": "The grace of our Lord Jesus Christ, and the love of God, and the fellowship of the Holy Spirit, be with us all evermore.",
                "people": "Amen.",
                "citation": "2 CORINTHIANS 13:14",
            }
        if self.office.date.date.weekday() in (0, 3):
            return {
                "officiant": "May the God of hope fill us with all joy and peace in believing through the power of the Holy Spirit. ",
                "people": "Amen.",
                "citation": "ROMANS 15:13",
            }

        if self.office.date.date.weekday() in (1, 4):
            return {
                "officiant": "Glory to God whose power, working in us, can do infinitely more than we can ask or imagine: Glory to him from generation to generation in the Church, and in Christ Jesus for ever and ever.",
                "people": "Amen.",
                "citation": "EPHESIANS 3:20-21",
            }

    def get_lines(self):

        grace_rotation = self.office.settings["grace"]

        easter = self.office.date.season.name == "Eastertide"

        officiant = "Let us bless the Lord."
        people = "Thanks be to God."

        if easter:
            officiant = "{} Alleluia, alleluia.".format(officiant)
            people = "{} Alleluia, alleluia.".format(people)

        lines = [
            Line("Dismissal and Grace", "heading"),
            Line(officiant, "leader_dialogue"),
            Line(people, "congregation_dialogue"),
        ]

        if grace_rotation == "fixed":
            grace = self.get_grace()
        else:
            grace = self.get_fixed_grace()

        return (
            lines
            + [Line("", "spacer")]
            + [
                Line(grace["officiant"], "leader"),
                Line("Amen.", "congregation"),
                Line(grace["citation"], "citation"),
            ]
        )


class GreatLitany(ShowGreatLitanyMixin, Module):
    office_name = "office"

    def get_names(self):
        feasts = self.office.date.all_evening if self.office_name == "evening_prayer" else self.office.date.all
        names = [feast.saint_name for feast in feasts if hasattr(feast, "saint_name") and feast.saint_name]
        names = ["the Blessed Virgin Mary"] + names
        return ", ".join(names)

    def get_leaders(self):
        setting = self.office.settings["national_holidays"]
        if setting == "us":
            return "your servant Joe Biden, the President of the United States of America, "
        if setting == "canada":
            return "your servants Her Majesty Queen Elizabeth, the Sovereign, and Justin Trudeau, the Prime Minister of Canada, "
        return "your servant Joe Biden, the President of the United States of America, your servants Her Majesty Queen Elizabeth, the Sovereign, and Justin Trudeau, the Prime Minister of Canada, Andrés Manuel López Obrador, the president of Mexico, "

    def get_lines(self):
        if self.show_great_litany:
            style = self.office.settings["language_style"]
            kyrie = (
                file_to_lines("kyrie_contemporary") if style == "contemporary" else file_to_lines("kyrie_traditional")
            )
            pater = (
                file_to_lines("pater_contemporary") if style == "contemporary" else file_to_lines("pater_traditional")
            )
            lines = (
                file_to_lines("great_litany")
                + [Line("", "spacer")]
                + kyrie
                + [Line("", "spacer")]
                + pater
                + [Line("", "spacer")]
                + file_to_lines("supplication")
            )
            for line in lines:
                line["content"] = line["content"].replace("{{ names }}", self.get_names())
                line["content"] = line["content"].replace("{{ leaders }}", self.get_leaders())
            return lines
        return None


class MPGreatLitany(GreatLitany):
    office_name = "morning_prayer"


class EPGreatLitany(GreatLitany):
    office_name = "evening_prayer"


class MorningPrayer(Office):
    def get_modules(self):
        return [
            MPOpeningSentence(self),
            Confession(self),
            Preces(self),
            MPInvitatory(self),
            MPPsalms(self),
            MPFirstReading(self),
            MPFirstCanticle(self),
            MPSecondReading(self),
            MPSecondCanticle(self),
            MPThirdReading(self),
            Creed(self),
            Prayers(self),
            MPCollectOfTheDay(self),
            MPAdditionalCollects(self),
            MPMissionCollect(self),
            MPGreatLitany(self),
            Intercessions(self),
            FinalPrayers(self),
            Dismissal(self),
        ]


class EveningPrayer(Office):
    def get_modules(self):
        return [
            EPOpeningSentence(self),
            Confession(self),
            Preces(self),
            EPInvitatory(self),
            EPPsalms(self),
            EPFirstReading(self),
            EPFirstCanticle(self),
            EPSecondReading(self),
            EPSecondCanticle(self),
            EPThirdReading(self),
            Creed(self),
            Prayers(self),
            EPCollectOfTheDay(self),
            EPAdditionalCollects(self),
            EPMissionCollect(self),
            EPGreatLitany(self),
            Intercessions(self),
            FinalPrayers(self),
            Dismissal(self),
        ]


class OfficeAPIView(APIView):
    permission_classes = [ReadOnly]

    def get(self, request, year, month, day):
        raise NotImplementedError("You must implement this method.")


class OfficeSerializer(serializers.Serializer):
    calendar_day = DaySerializer(source="date")
    modules = serializers.SerializerMethodField()

    def get_modules(self, obj):
        modules = [module.json for module in obj.get_modules()]
        modules = [module for module in modules if module and module["lines"]]
        return modules


class MorningPrayerView(OfficeAPIView):
    def get(self, request, year, month, day):
        office = MorningPrayer(request, year, month, day)
        serializer = OfficeSerializer(office)
        return Response(serializer.data)


class EveningPrayerView(OfficeAPIView):
    def get(self, request, year, month, day):
        office = EveningPrayer(request, year, month, day)
        serializer = OfficeSerializer(office)
        return Response(serializer.data)


class SettingOptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = SettingOption
        fields = (
            "uuid",
            "name",
            "description",
            "value",
            "order",
        )


class SettingSerializer(serializers.ModelSerializer):
    options = SettingOptionSerializer(many=True, source="settingoption_set")
    site_name = serializers.SerializerMethodField()
    setting_type_name = serializers.SerializerMethodField()

    def get_site_name(self, obj):
        sites = dict(Setting.SETTING_SITES)
        return sites[obj.site]

    def get_setting_type_name(self, obj):
        setting_types = dict(Setting.SETTING_TYPES)
        return setting_types[obj.setting_type]

    class Meta:
        model = Setting
        fields = (
            "uuid",
            "name",
            "title",
            "description",
            "site",
            "site_name",
            "setting_type",
            "setting_type_name",
            "order",
            "options",
        )


class AvailableSettings(mixins.ListModelMixin, viewsets.GenericViewSet):
    serializer_class = SettingSerializer
    queryset = Setting.objects.prefetch_related("settingoption_set").order_by("site", "setting_type", "order").all()


# heading
# subheading
# citation
# html
# leader
# congregation
# rubric
# leader_dialogue
# congregation_dialogue


def heading(content):
    return "<h2>{}</h2>".format(content)


def subheading(content):
    return "<h4>{}</h4>".format(content)


def citation(content):
    return "<h5>{}</h5>".format(content)


def html_content(content):
    return content


def leader(content, indented=False):
    if indented:
        return "<p class='indent'>{}</p>".format(content)
    return "<p class='handing-indent'>{}</p>".format(content)


def congregation(content, indented=False):
    if indented:
        return "<p class='indent'><strong>{}</strong></p>".format(content)
    return "<p class='handing-indent'><strong>{}</strong></p>".format(content)


def rubric(content):
    return "<p><em>{}</em></p>".format(content)


def leader_dialogue(content, indented=False):
    return leader(content, indented)


def congregation_dialogue(content, indented=False):
    return congregation(content, indented)


def line_to_html(line):
    if line["line_type"] == "heading":
        return heading(line["content"])
    if line["line_type"] == "subheading":
        return subheading(line["content"])
    if line["line_type"] == "citation":
        return citation(line["content"])
    if line["line_type"] == "html":
        return html_content(line["content"])
    if line["line_type"] == "leader":
        return leader(line["content"], line["indented"])
    if line["line_type"] == "congregation":
        return congregation(line["content"], line["indented"])
    if line["line_type"] == "rubric":
        return rubric(line["content"])
    if line["line_type"] == "leader_dialogue":
        return leader_dialogue(line["content"], line["indented"])
    if line["line_type"] == "congregation_dialogue":
        return congregation_dialogue(line["content"], line["indented"])
    return line["content"]


def json_modules_to_html(modules, request=None):
    html = ""
    for module in modules:
        for line in module["lines"]:
            html += line_to_html(line)
    return render_to_string("display_base.html", {"content": mark_safe(html)})


class MorningPrayerDisplayView(OfficeAPIView):
    def get(self, request, year, month, day):
        office = MorningPrayer(request, year, month, day)
        serializer = OfficeSerializer(office)
        return HttpResponse(json_modules_to_html(serializer.data["modules"], request), content_type="text/html")