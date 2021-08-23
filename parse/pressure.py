# -*- coding: utf-8 -*-
"""
chemdataextractor.parse.operating_temperature.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~
Parser for temperature.
"""
import logging
from lxml import etree
import traceback
import re
from ..parse import R, T, I, W, Optional, merge, join,Any, OneOrMore, Not, ZeroOrMore, SkipTo
from ..parse.cem import cem, chemical_label, lenient_chemical_label, solvent_name
from ..parse.common import lbrct, dt, rbrct, comma
from ..model import BaseModel, StringType, ListType, ModelType
from ..model import Compound
from ..parse.base import BaseParser
from ..utils import first
from ..parse.cem import cem, chemical_label,lenient_chemical_label,solvent_name
# log = logging.getLogger(__name__)

delim = R('^[:;\.,]$')

'''1. 确定压力的单位'''
pressunits = ((R('[^[KkM]?Pa$',re.I)|R('^bar$')+ Not(I('/')))('pressunits')).add_action(merge)

'''2.确定压力的值'''
joined_range = R(r'^[\+\-–−]?\d+(\.\\d+)?(\(\d\))?[\-––-−~∼˜]\d+(\.\d+)?(\(\d\))?$')('value').add_action(join)
spaced_range = (R(r'^[\+\-–−]?\d+(\.d+)?(\(\d\))?$') + Optional(pressunits).hide() + (R(r'^[\-±–−~∼˜]$') + R(r'^[\+\-–−]?\d+(\.\d+)?(\(\d\))?$') | R(r'^[\+\-–−]\d+(\.\d+)?(\(\d\))?$')))('value').add_action(join)
to_range = (ZeroOrMore(R(r'^[\+\-–−]?\d+(\.\d+)?(\(\d\))?$') + Optional(pressunits).hide()) + Optional(I('to')).hide() + R(r'^[\+\-–−]?\d+(\.\d+)?(\(\d\))?$'))('value').add_action(join)
and_range = (ZeroOrMore(R(r'^[\+\-–−]?\d+(\.\d+)?(\(\d\))?$') + Optional(pressunits).hide() + Optional(comma)) + Optional(I('and') | comma) + R(r'^[\+\-–−]?\d+(\.\d+)?(\(\d\))?$'))('value').add_action(join)
range = (Optional(R(r'^[\-–−]$')) + (and_range | to_range | spaced_range | joined_range)).add_action(join)
value = (Optional(R(r'^[\-–−]$')) + Optional(R(r'^[~∼˜\<\>\≤\≥]$')) + Optional(R(r'^[\-\–\–\−±∓⨤⨦±]$')) + R(r'^\d+(\.\d+)?$')).add_action(join)
power = (Optional(R(r'^[\+\-–−]?\d+(\.\d+)?$') + R('×')) + (R('10') + W('−') + R(r'\d') | R(r'^10[\-–−]?\d+$'))).add_action(join)
pressvalue = (power | range| value)('pressvalue')
# pressure = (pressvalue + pressunits)('pressure')
'''3.压力的前缀'''
press_specifier = (
                  Optional(I('bed'))+  Optional(I('operating')) +
                  Optional(I('elevated')) + Optional(I('atmospheric'))+ Optional(I('absolute'))+
                  (R('^P$')|I('pressure') | I('pressures')))('specifier')

prefix = (press_specifier
         + Optional(I('varies') + I('from')).hide() \
         + Optional(R('^increase[sd]/$') | R('^decrease[sd]/$')).hide() \
         + Optional(W('=') | W('~') | W('≈') | W('≃') |  I('of') | I('was') | I('is') | I('are') | I('be') | I('at') | I('near') | I('above') | I('below') | I('were')).hide() \
         + Optional(I('reported') | I('determined')).hide()\
         + Optional(I('as') | I('for') | (I('to'))).hide() \
         + Optional(I('in') + I('the') + I('range')).hide()\
         + Optional(I('of') | I('about') | I('around') | I('approximately') | (I('high') + I('as'))).hide())

press_specifier_and_value = (prefix + Optional(delim).hide() + Optional(lbrct | I('[')).hide() +
                            Optional(press_specifier).hide() + pressvalue + pressunits + Optional(rbrct | I(']')).hide())('pressure')




class OperatingPre(BaseModel):
    pressvalue = StringType()
    pressunits = StringType()
Compound.pressure = ListType(ModelType(OperatingPre))

class TextPressParser(BaseParser):
    root = press_specifier_and_value
    def interpret(self, result, start, end):
        compound = Compound(
           pressure =[
               OperatingPre(
                    pressvalue=first(result.xpath('./pressvalue/text()')),
                    pressunits=first(result.xpath('./pressunits/text()'))
                )
            ]
        )
        yield compound
# Paragraph.parsers = [TextPressParser()]

#
# d = Document(
#     # Heading(u'Synthesis of 2,4,6-trinitrotoluene (3a)'),
#     Paragraph(u'The particles were smooth spherical glass beads with a Sauter mean diameter of 321 µm. Umf values at 20 °C were found experimentally '
#               u'to be 0.33, 0.26, 0.24 and 0.22 m/s for freeboard pressures of 379, 448, 587 and 724 kPa, respectively. When the temperature increase to (40 °C), '
#               u'Umf values is 0.23, 0.25, 0.35 and 0.52 m/s. '),
#     Paragraph(u'the diameter of polyethylene resin (HDPE) glass beads is 321 µm'),
#     Paragraph(u' Umf for HDPE particles at 20 °C was found experimentally to be 0.14, 0.11 and 0.09 m/s for pressures of 379, 586 and 724 kPa, respectively.')
#              )
# print(d.elements)
# print(d.records.serialize())


