# -*- coding: utf-8 -*-
"""
chemdataextractor.parse.apparatus.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Parser for sentences that provide experimental and material information.

"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals
import logging
import re

from .common import optdelim, hyphen, slash
from ..utils import first
from ..parse.base import BaseParser
from ..model import Compound
from .actions import join, merge, fix_whitespace
# from .cem import chemical_name
from .elements import I, T, R, W, ZeroOrMore, Optional, Group, OneOrMore, Any, Not
from ..model import BaseModel, StringType, ListType, ModelType

log = logging.getLogger(__name__)

#
# apparatus_type = R('^\d{2,}$') + W('MHz')
shape_type = (R('cylindrical|cuboid|2D|3D|plexiglas|acrylic|tapered|circular', re.I))

instrument = (OneOrMore(shape_type) + Optional(I('perspex')|I('bed')|(I('stainless') + I('steel'))) + (I('tubing')|I('shape')|I('column') | (R('fluidi') + R('bed')))).add_action(join)

instrument_blcklist = R('filled', re.I)

instrument = (instrument + Not(instrument_blcklist)).add_action(join)('instrument')
# apparatus = (ZeroOrMore(T('JJ'))  + ZeroOrMore(T('NNP') | T('NN'))
#              + ZeroOrMore(T('NNP') | T('NN') | T('HYPH') | T('CD') )
#              + Optional(instrument))('apparatus').add_action(join).add_action(fix_whitespace)

# apparatus_blacklist = R('^(following|usual|equation|standard|accepted|method)$', re.I)

# apparatus_phrase = (W('with') | W('using') | W('on')).hide() + Not(apparatus_blacklist) + apparatus
#
# apparatus_phrase = OneOrMore(apparatus_phrase | Any().hide())('apparatus_phrase')
# apparatus_phrase = apparatus('apparatus_phrase')
apparatus_phrase = instrument('apparatus_phrase')
class Apparatus(BaseModel):
    apparatus_name = StringType()
Compound.apparatus = ListType(ModelType(Apparatus))

class ApparatusParser(BaseParser):
    """"""
    root = apparatus_phrase
    # print(root)
    def interpret(self, result, start, end):
        # print(end)
        compound = Compound(
            apparatus =[
                Apparatus(
                    apparatus_name = first(result.xpath('./text()'))
                )]
        )
        # print(Apparatus.apparatus_name)
        if Apparatus.apparatus_name:
            yield compound
