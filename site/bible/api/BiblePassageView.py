import urllib

from rest_framework import serializers
from rest_framework.response import Response
from rest_framework.views import APIView

from bible.passage import Passage
from churchcal.api.permissions import ReadOnly


class BiblePassageHeadingsSerializer(serializers.Serializer):
    verse = serializers.SerializerMethodField()
    heading = serializers.SerializerMethodField()

    def get_verse(self, obj):
        return obj[0]

    def get_heading(self, obj):
        return obj[1]


class BiblePassageSerializer(serializers.Serializer):
    html = serializers.CharField()
    text = serializers.CharField()
    headings = BiblePassageHeadingsSerializer(many=True)
    version_abbreviation = serializers.CharField()
    version_name = serializers.CharField()


class BiblePassageView(APIView):
    permission_classes = [ReadOnly]

    def get(self, request, passage, version="NRSVCE"):
        version = version.upper()
        if version == "NRSV":
            version = "NRSVCE"
        print(passage)
        passage = urllib.parse.unquote(passage)
        passage = urllib.parse.unquote_plus(passage)
        print(passage)
        passage = Passage(passage, source=version)
        serializer = BiblePassageSerializer(passage)
        return Response(serializer.data)
