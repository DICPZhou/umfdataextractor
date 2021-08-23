# -*- coding: utf-8 -*-
"""
chemdataextractor.parse.operating_temperature.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~
Parser for temperature.
"""
import logging
from lxml import etree
import traceback

from ..parse import R, T, I, W, Optional, merge, join,Any, OneOrMore, Not, ZeroOrMore, SkipTo
from ..parse.cem import cem, chemical_label, lenient_chemical_label, solvent_name
from ..parse.common import lbrct, dt, rbrct, comma
from ..model import BaseModel, StringType, ListType, ModelType
from ..model import Compound
from ..parse.base import BaseParser
from ..utils import first
from ..parse.cem import cem, chemical_label,lenient_chemical_label,solvent_name
# log = logging.getLogger(__name__)
import re
delim = R('^[:;\.,]$')

'''1. 确定颗粒密度的单位'''
particle_density_units = ((R('[k]?g') +R('[c]?m[\-–−]3'))|(R('[k]?g')+W('/')+R('[c]?m')))('particle_density_units').add_action(merge)

'''2.确定颗粒密度的值'''
joined_range = R(r'^[\+\-–−]?\d+(\.\\d+)?(\(\d\))?[\-––-−~∼˜]\d+(\.\d+)?(\(\d\))?$')('value').add_action(join)
spaced_range = (R(r'^[\+\-–−]?\d+(\.d+)?(\(\d\))?$') + Optional(particle_density_units).hide() + (R(r'^[\-±–−~∼˜]$') + R(r'^[\+\-–−]?\d+(\.\d+)?(\(\d\))?$') | R(r'^[\+\-–−]\d+(\.\d+)?(\(\d\))?$')))('value').add_action(join)
to_range = (ZeroOrMore(R(r'^[\+\-–−]?\d+(\.\d+)?(\(\d\))?$') + Optional(particle_density_units).hide()) + Optional(I('to')).hide() + R(r'^[\+\-–−]?\d+(\.\d+)?(\(\d\))?$'))('value').add_action(join)
and_range = (ZeroOrMore(R(r'^[\+\-–−]?\d+(\.\d+)?(\(\d\))?$') + Optional(particle_density_units).hide() + Optional(comma)) + Optional(I('and') | comma).hide() + R(r'^[\+\-–−]?\d+(\.\d+)?(\(\d\))?$'))('value').add_action(join)
range = (Optional(R(r'^[\-–−]$')) + (and_range | to_range | spaced_range | joined_range)).add_action(join)
value = (Optional(R(r'^[\-–−]$')) + Optional(R(r'^[~∼˜\<\>\≤\≥]$')) + Optional(R(r'^[\-\–\–\−±∓⨤⨦±]$')) +R('^[\+\-–−]?\d+(\.\d+)?(\(\d\))?$')).add_action(join)
power = (Optional(R(r'^[\+\-–−]?\d+(\.\d+)?$') + R('×')) + (R('10') + W('−') + R(r'\d') | R(r'^10[\-–−]?\d+$'))).add_action(join)
particle_density_value = (power | range| value)('particle_density_value')


'''3.颗粒密度的前缀'''
particle_den_specifier = ((R('pp|ρp',re.I)
                           |(Optional(R('particle')|W('average'))+ R('densit'))
                           |I('and'))
                           |(R('particle'))
                           + Optional(I('value')))('specifier')

prefix = (particle_den_specifier
          + Optional(W('=') | W('~') | W('≈') | W('≃') | I('was') | I('is') | I('are') | I('be') | I('at') | I('near') | I('above') | I('below') | I('were')).hide()
          + Optional(I('of')|('between')).hide()
          + Optional(R('particle')|(I('quartz') + R('sand'))).hide()
          + Optional(I('used') + I('in') + I('this') + I('paper')|I('work')|I('research')|I('stduy')).hide() #
          + Optional( I('was') | I('is') | I('are')| I('were')).hide()
          + Optional(R('increase') | R('decrease')).hide()
          + Optional(I('as') | I('for') | (I('to'))).hide()
          + Optional(I('in') + I('the') + I('range')).hide()
          + Optional(I('of') | I('about') | I('around') | I('approximately') | (I('high') + I('as'))).hide())

density_specifier_and_value = (prefix + Optional(delim).hide() + Optional(lbrct | I('[')).hide() + particle_density_value + particle_density_units + Optional(rbrct | I(']')).hide())('particle_density')




class Particle_density(BaseModel):
    particle_density_value = StringType()
    particle_density_units = StringType()
Compound.particle_density = ListType(ModelType(Particle_density))

class TextParticledensityParser(BaseParser):
    root = density_specifier_and_value
    def interpret(self, result, start, end):
        compound = Compound(
           particle_density =[
               Particle_density(
                    particle_density_value=first(result.xpath('./particle_density_value/text()')),
                    particle_density_units=first(result.xpath('./particle_density_units/text()'))
                )
            ]
        )
        yield compound
# Paragraph.parsers = [TextParticledensityParser()]

#
# d = Document(
#     Paragraph(u'the ρp is 1000 kg/m3')
#              )
# print(d.records.serialize())


