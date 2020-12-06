# -*- coding: utf-8 -*-
"""
chemdataextractor.parse.table
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~



"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals
import logging
import re
from lxml.builder import E

from ..utils import first
from ..model import Compound, Velocity, GasViscosity, GasDensity
from ..model import ParticleDiameter, ParticleDensity, GasDensity, GasViscosity, Velocity, Sphericity, BedVoidage, TabelPress, TabelTemp
# from ..model import  UvvisSpectrum, UvvisPeak, QuantumYield, FluorescenceLifetime, MeltingPoint, GlassTransition
# from ..model import ElectrochemicalPotential, IrSpectrum, IrPeak
from .actions import join, merge, fix_whitespace
from .base import BaseParser
# from .cem import chemical_label, label_before_name, chemical_name, chemical_label_phrase, solvent_name, lenient_chemical_label
from .cem import particle_label, lenient_particle_label
from .elements import R, I, W, Optional, ZeroOrMore, Any, OneOrMore, Start, End, Group, Not, T
from ..parse.common import lbrct, rbrct, comma, stop
log = logging.getLogger(__name__)
delims = ZeroOrMore(R(r'^[,:;/\.\[\]\(\)\{\}]$').hide())
minus = R(r'^[\-–−‒]$')
name_blacklist = R(r'^([\d\.]+)$')

# 需要在专门增加一列为：单位 （unit（s）或者comment 待完善

'''1. 颗粒属性定义'''
#: Compound identifier column heading
compound_heading = R('(^|\b)(comp((oun)?d)?|Geldart group|\b)', re.I)  # solid,|particle

compound_cell = Group((Start() + particle_label + End())('material') | (Start() + lenient_particle_label + End())('material'))('material_phrase')

'''2.颗粒直径定义'''
particle_diameter_title = (
    R('^ds$|d32|APS|dv$|dsv$') |
    (R('[Pp]article') + R('diameter') + Optional(comma) + R('[dσ]')) |
    (R('Particle[s]?|Average|Mean|[Ss]olid|[Dd]?sauter|Sand|Surface|Equivalent|True|Arithmetic|Sauter|[Ww]eighted|Brouckere|Harmonic')
     + Optional(W('solid')) + Optional(R('mean|average')) + Optional(R('particle|material')) + R('size|diam', re.I) + Optional('of') + Optional(R('particle'))
     + Optional(lbrct) + Optional(comma) + Optional(R('dP?', re.I)) + Optional(R('f$|p$|ρ$'))) |
    (R('particle') + R('size|diameter') + Not(W('×'))) |  # 排除形状为圆柱形的物体
    (R('Diameter') + Optional(lbrct) + W('dp') + Optional(rbrct)) |
    (R('Diameter') + Optional(W('of') | comma) + Optional(W('the')) + Not(W('gas')) + Not(W('bed')) + Not(W('column')) + R('particle|dp$|range|d$', re.I)) |
    (R('avg') + Optional(stop) + R('diam')) |
    (R('dp$') + W(',') + R('avg|sph|L$|D$|SM$')) |
    (Start() + R('dp$') + W(',') + R('m|s')) |
    (Start() + R('^[Dd][Pp]?$') + Optional(R('p$', re.I)) + Not(W('<'))) |  #  | W('/')
    (Start() + R('^d$') + R('p$', re.I) + Not(W('<') | W('/'))) |
    (Start() + R('dpe$')) |  # pe: mixing particles
    (Start() + W('Diameter') + Optional(comma) + Not(W('mm') | W('of') | (W('[') + W('m')))) |
    (Start() + R('^Size$') + (W(',') | W('(')) + Optional(R('dp$'))) |
    (W('Size') + W('range') + Optional(comma) + R('d')) |
    (R('Mean') + R('^dp$')) |
    (Start() + R('^ds$', re.I) + Optional(comma) + R('d')) |
    (Start() + R('dp$') + End()) |
    (R('d‾p|d¯p|dp¯|d̄p|dp‾|dpm$|dSauter|dpi$|^di$')) |
    (R('[vV]olume') + R('mean') + R('diameter')) |
    (R('[vV]olume') + W('to') + W('surface') + R('diameter')) |
    (R('weighted') + R('mean') + R('dia')) |
    (I('sieve') + W('size')) |
    # (Start() + R('^D$') + W('[')) |
    (Start() + R('^d$') + W('#') + W('[')) |
    (Start() + R('^d$') + W('('))

)

particle_diameter_units = (
        (R('μ|μ', re.I) + W('m')) |
        # (R('Μ') + W('m')) |  # 有的表格用Μm表示微米,Μ（大写Μ，小写μ）
        (R('[µµncm]?m$')) |
        (R('㎛')) |
        (R('mesh')) |
        (R('[ncm]m$'))
)('particle_diameter_units').add_action(merge)

particle_diameter_heading = (Not(W('deviation')) + OneOrMore(particle_diameter_title.hide()) + Optional(delims.hide())
                             + Optional(W('mean').hide()) + Optional(delims.hide()) + Optional(particle_diameter_units)
                             )('particle_diameter_heading')

joined_range = R(r'^[\+\-–−]?\d+(\.\\d+)?(\(\d\))?[\-––-−~∼˜]\d+(\.\d+)?(\(\d\))?$')('value').add_action(join)

spaced_range = (
        R(r'^[\+\-–−]?\d+(\.d+)?(\(\d\))?$') + Optional(particle_diameter_units).hide() +
        (R(r'^[\-±–−~∼˜]$') + R(r'^[\+\-–−]?\d+(\.\d+)?(\(\d\))?$') | R(r'^[\+\-–−]\d+(\.\d+)?(\(\d\))?$'))
)('value').add_action(join)

spaced_range1 = (
        OneOrMore(R(r'^[\+\-–−]?\d+(\.d+)?(\(\d\))?$') + R(r'^[\-±–−~∼˜]$') + R(r'^[\+\-–−]?\d+(\.\d+)?(\(\d\))?$'))
)('value').add_action(join)

to_range = (ZeroOrMore(R(r'^[\+\-–−]?\d+(\.\d+)?(\(\d\))?$') + Optional(particle_diameter_units).hide()) + Optional(I('to')) + R(r'^[\+\-–−]?\d+(\.\d+)?(\(\d\))?$')
            )('value').add_action(join)

to_range2 = (
        (R(r'^[\+\-–−]?\d+(\.\d+)?(\(\d\))?$') + I('<') + Optional(W('dp'))) + I('<') + R(r'^[\+\-–−]?\d+(\.\d+)?(\(\d\))?$')
            )('value').add_action(join)

and_range = (OneOrMore(R(r'^[\+\-–−]?\d+(\.\d+)?(\(\d\))?$') + Optional(particle_diameter_units).hide() + comma)
             + R(r'^[\+\-–−]?\d+(\.\d+)?(\(\d\))?$')
             )('value').add_action(join)

and_range1 = (OneOrMore(R(r'^[\+\-–−]?\d+(\.\d+)?(\(\d\))?$') + Optional(particle_diameter_units).hide() + Optional(comma))
             + Optional(I('and') | comma).hide() + R(r'^[\+\-–−]?\d+(\.\d+)?(\(\d\))?$'))('value').add_action(join)

range1 = (and_range | and_range1 | to_range2 | to_range | spaced_range1 | spaced_range | joined_range).add_action(join)

value = (Optional(R(r'^[\-–−]$')) + Optional(R(r'^[~∼˜\<\>\≤\≥]$')) + Optional(R(r'^[\-\–\–\−±∓⨤⨦±]$'))
         + R(r'^[\+\-–−]?\d+(\.\d+)?(\(\d\))?$') + Optional(R(r'^[\-\–\–\−\+±∓⨤⨦±]$'))
         + ZeroOrMore(R(r'^[\+\-–−]?\d+(\.\d+)?(\(\d\))?$'))
         )('value').add_action(join)

power = (
    (OneOrMore(R(r'\d+(\.\d+)?') + R('×|·') + (R('10') + R('[-−–−]') + R(r'\d+') | R(r'^10[\-–−]?\d+$')))) |
    (OneOrMore(R(r'\d+(\.\d+)?·10') + R('[-−–−]') + R(r'\d+'))) |
    (R(r'\d+(\.\d+)?') + R('E', re.I) + Optional(R('[-−–−]')) + R(r'\d+')) |
    (R(r'\d+(\.\d+)?[Ee]') + Optional(R('[-−–−]')) + R(r'\d+')) |
    (R(r'\d+(\.\d+)?[Ee]?') + W('-') + R(r'\d+'))
).add_action(join)

particle_diameter_value = (power | range1 | value)('particle_diameter_value')

table_particle_diameter_cell = (OneOrMore(particle_diameter_value) + Optional(delims.hide()) + Optional(particle_diameter_units))('particle_diameter_cell')

'''3. 颗粒密度定义'''
particle_density_title = (
    (R('[Pp]articles?|Theoreti|Real|[Mm]aterial|True|Actual|[Ss]olid|Bed|[Ss]kelet|Jetsam|[Aa]pparent') + Optional(W('particle'))
     + Optional(W('solid')) + R('[Dd]ens') + Optional(W(',') | W('(')) + Optional(R('^ρ[ps]?')) + Optional(R('^s|^p|^f', re.I))) |
    (R('[Dd]ensity') + W('of') + R('sorbent|particles?') + Optional(comma) + R('ρ[Ps]?$', re.I) + Optional(
        R('[ps]', re.I))) |
    (R('Density') + Optional(lbrct) + W('ρ') + Optional(rbrct)) |
    (R('Density') + Optional(comma) + Optional(W('of')) + Optional(comma) + R('ρ[^g]?P|particle')) |
    (R('[Dd]ensity') + Optional(comma) + Optional(W('of')) + Optional(comma) + R('ρ$') + R('[ps]', re.I) + Optional(W('['))) |
    (Start() + R('^ρ[Pps]?$', re.I) + Optional(R('^[Pps]$', re.I)) + W('(') + Optional(R('part') + R('dens'))) |
    (Start() + R('^ρ$', re.I) + R('^[ps]$', re.I) + W(',') + R('real|d')) |
    (Start() + R('^ρ$', re.I) + R('^[ps]$', re.I) + Not(W('/') + R('^ρ$', re.I))) |  # + Not(W('/'))) |  # ρap: apparent density
    (W('Density') + W('of') + W('bed') + R('materials?')) |
    (R('^ρ$|ρ$', re.I) + End()) |
    (R('^ρ$', re.I) + R('L$|D$|mf?$|sk$|ps$|pe$|^[Ss]$')) |  # pe: mixing particles
    (Start() + R('ρP$|ρP$|Pp$', re.I)) |
    (W('Density') + W('of') + W('solid') + R('particles?')) |
    (Start() + R('Density') + W(',')) |
    (Start() + R('Density') + W('/')) |
    (Start() + R('Density') + R('[Kk]?g') + W('/')) |
    (Start() + R('Density') + W('[')) |
    (Start() + R('^Density$') + Not(Any())) |
    (Start() + R('^ρ$', re.I) + Not(T('NN') | W('f'))) |
    (Start() + R('Density') + W('('))
    # 在分词的时候将ρ和后面的单词分开了，所以这儿需要单独拆开进行匹配
)

particle_density_units = (
        (R('kg·?m') + R('[-–−]') + R('3')) |
        (R('[Kk]?g') + W('/') + R('c?m3?')) + Optional(R('3')) |
        (R('[Kk]?g') + R('c?m$') + R('[-–−−]') + R('3')) |
        (R('[Kk]?g') + Optional(stop) + R(r'[c]?m[\-–−]?3?')) |
        (R('c?m3?') + Optional(R('3')))
)('particle_density_units').add_action(merge)

particle_density_heading = (
        OneOrMore(particle_density_title.hide()) + Optional(delims.hide()) + Optional(particle_density_units)
)('particle_density_heading')


joined_range = R(r'^[\+\-–−]?\d+(\.\\d+)?(\(\d\))?[\-––-−~∼˜]\d+(\.\d+)?(\(\d\))?$')('value').add_action(join)

spaced_range = (R(r'^[\+\-–−]?\d+(\.d+)?(\(\d\))?$') + Optional(particle_density_units).hide() + (R(r'^[\-±–−~∼˜]$') + R(r'^[\+\-–−]?\d+(\.\d+)?(\(\d\))?$') | R(r'^[\+\-–−]\d+(\.\d+)?(\(\d\))?$')))('value').add_action(join)

to_range = (OneOrMore(R(r'^[\+\-–−]?\d+(\.\d+)?(\(\d\))?$') + Optional(particle_density_units).hide()) + I('to') + R(r'^[\+\-–−]?\d+(\.\d+)?(\(\d\))?$'))('value').add_action(join)

to_range2 = ((R(r'^[\+\-–−]?\d+(\.\d+)?(\(\d\))?$') + I('<') + Optional(W('dp'))) + I('<') + R(r'^[\+\-–−]?\d+(\.\d+)?(\(\d\))?$'))('value').add_action(join)

and_range = (OneOrMore(R(r'^[\+\-–−]?\d+(\.\d+)?(\(\d\))?$') + Optional(particle_density_units).hide() + Optional(comma))
             + Optional(I('and') | comma).hide() + R(r'^[\+\-–−]?\d+(\.\d+)?(\(\d\))?$'))('value').add_action(join)

range1 = (and_range | to_range2 | to_range | spaced_range | joined_range).add_action(join)

value = (Optional(R(r'^[\-–−]$')) + Optional(R(r'^[~∼˜\<\>\≤\≥]$')) + Optional(R(r'^[\-\–\–\−±∓⨤⨦±]$'))
         + R(r'^[\+\-–−]?\d+(\.?\,?\d+)?(kg)?$') + Optional(R(r'^[\-\–\–\−±∓⨤⨦±]$'))
         + ZeroOrMore(R(r'^[\+\-–−]?\d+(\.\d+)?(\(\d\))?$'))
         )('value').add_action(join)

power = (
    (OneOrMore(R(r'\d+(\.\d+)?') + R('×') + (R('10') + R('[-−–−]') + R(r'\d+') | R(r'^10[\-–−]?\d+$')))) |
    (R(r'\d+(\.\d+)?') + R('E', re.I) + Optional(R('[-−–−]')) + R(r'\d+')) |
    (R(r'\d+(\.\d+)?') + R(r'x10[\-–−]?\d+$')) |
    (OneOrMore(R(r'\d+(\.\d+)?·10') + R('[-−–−]') + R(r'\d+'))) |
    (R(r'\d+(\.\d+)?[Ee]?') + W('-') + R(r'\d+'))
).add_action(join)

particle_density_value = (power | range1 | value)('particle_density_value')

particle_density_cell = (
        OneOrMore(particle_density_value) + Optional(delims.hide()) + Optional(particle_density_units)
)('particle_density_cell')


'''颗粒球形度'''

particle_sphericity_title = (
    (R('spheric|roundness|shape', re.I) + Optional(lbrct) + Optional(R('ϕ|spheric', re.I)) + Optional(rbrct)) |
    (R('Ø|ϕ|Φ', re.I) + (W('s$')| W('p$'))) |
    (R('[ϕΦ][sP]$', re.I)) |
    (R('Φs')) |
    (R('shape', re.I) + R('coefficient', re.I))
)('particle_sphericity_title')

particle_sphericity_heading = (OneOrMore(particle_sphericity_title).hide())('particle_sphericity_heading')

value = (Optional(R(r'^[\-–−]$')) + Optional(R(r'^[~∼˜\<\>\≤\≥]$')) + Optional(R(r'^[\-\–\–\−±∓⨤⨦±]$'))
         + R(r'^[\+\-–−]?\d+(\.\d+)?(\(\d\))?$') + Optional(R(r'^[\-\–\–\−±∓⨤⨦±]$'))
         + ZeroOrMore(R(r'^[\+\-–−]?\d+(\.\d+)?(\(\d\))?$'))
         )('value').add_action(join)

value1 = R(r'\.\d+')

particle_sphericity_value = (value | value1)('particle_sphericity_value')

particle_sphericity_cell = particle_sphericity_value('particle_sphericity_cell')


'''最小流化时床层空隙率'''
bed_voidage_title = (
    (Optional(R('bed', re.I)) + R('voidage|ε|ɛ', re.I) + Optional(W('g') | W('s')| W('m')) + Optional(delims) + Optional(lbrct) + Optional(R('mf', re.I))
     + Optional(R('ε', re.I)) + Optional(rbrct) + Not(R('[^bax]'))) |
    (R('fraction', re.I) + W('at') + R('minimum', re.I) + R('fluidiz', re.I) + R('vel', re.I)) |
    (R('minimum', re.I) + W('void') + R('age', re.I)) |
    (R('solids?', re.I) + R('fraction', re.I))
)('bed_voidage_title')


bed_voidage_heading = (OneOrMore(bed_voidage_title.hide()))('bed_voidage_heading')

value = (Optional(R(r'^[\-–−]$')) + Optional(R(r'^[~∼˜\<\>\≤\≥]$')) + Optional(R(r'^[\-\–\–\−±∓⨤⨦±]$'))
         + R(r'^[\+\-–−]?\d+(\.\d+)?(\(\d\))?$') + Optional(R(r'^[\-\–\–\−±∓⨤⨦±]$'))
         + ZeroOrMore(R(r'^[\+\-–−]?\d+(\.\d+)?(\(\d\))?$'))
         )('value').add_action(join)

value1 = R(r'\.\d+')

bed_voidage_value = (value | value1)('bed_voidage_value')

bed_voidage_cell = bed_voidage_value('bed_voidage_cell')

'''4.气体密度定义'''

gas_density_title = (
    (R('gas', re.I) + Optional(R('phase')) + R('dens') + Optional(W(',')) + R('ρ') + R('^g|^f')) |
    (R('^ρ', re.I) + Optional(R('^[fg]$', re.I)) + lbrct) |
    (Start() + R('^ρ', re.I) + OneOrMore(R('^[fg]$|gas$', re.I))) |
    (Start() + R('^ρ[fg]$')) |
    (R('gas|air|fluid|suspension', re.I) + Optional(R('phase')) + R('densi', re.I))
)

gas_density_units = (
        (R('kg·?m') + R(r'[-–−-]') + R('3')) |
        (R('[Kk]?g') + W('/') + R('c?m3?')) + Optional(R('3')) |
        (R('[Kk]?g') + R('[c]?m$') + R('[-–−]') + R('3')) |
        (R('[Kk]?g') + Optional(stop) + R(r'[c]?m[\-–−]?3?'))
)('gas_density_units').add_action(merge)

gas_density_heading = (gas_density_title.hide() + Optional(delims.hide()) + Optional(gas_density_units))('gas_density_heading')
# gas_density_heading = Group(Start() + gas_density_title.hide() + Optional(delims.hide()) + Optional(gas_density_units) + End())('gas_density_heading')

joined_range = OneOrMore(R(r'^[\+\-–−]?\d+(\.\d+)?(\(\d\))?[\-––-−~∼˜]\d+(\.\d+)?(\(\d\))?$'))('value').add_action(join)

spaced_range = (R(r'^[\+\-–−]?\d+(\.d+)?(\(\d\))?$') + Optional(gas_density_units).hide() + (R(r'^[\-±–−~∼˜]$') + R(r'^[\+\-–−]?\d+(\.\d+)?(\(\d\))?$') | R(r'^[\+\-–−]\d+(\.\d+)?(\(\d\))?$')))('value').add_action(join)

to_range = (ZeroOrMore(R(r'^[\+\-–−]?\d+(\.\d+)?(\(\d\))?$') + Optional(gas_density_units).hide()) + Optional(I('to')) + R(r'^[\+\-–−]?\d+(\.\d+)?(\(\d\))?$'))('value').add_action(join)

to_range2 = ((R(r'^[\+\-–−]?\d+(\.\d+)?(\(\d\))?$') + I('<') + Optional(W('dp'))) + I('<') + R(r'^[\+\-–−]?\d+(\.\d+)?(\(\d\))?$'))('value').add_action(join)

and_range = (OneOrMore(R(r'^[\+\-–−]?\d+(\.\d+)?(\(\d\))?$') + Optional(gas_density_units).hide() + Optional(comma))
             + Optional(I('and') | comma).hide() + R(r'^[\+\-–−]?\d+(\.\d+)?(\(\d\))?$'))('value').add_action(join)

range1 = (Optional(R(r'^[\-–−]$')) + (joined_range | and_range | to_range2 | to_range | spaced_range)).add_action(join)

value = (Optional(R(r'^[\-–−]$')) + Optional(R(r'^[~∼˜\<\>\≤\≥]$')) + Optional(R(r'^[\-\–\–\−±∓⨤⨦±]$'))
         + R(r'^[\+\-–−]?\d+(\.\d+)?(\(\d\))?$') + Optional(R(r'^[\-\–\–\−±∓⨤⨦±]$'))
         + ZeroOrMore(R(r'^[\+\-–−]?\d+(\.\d+)?(\(\d\))?$'))
         )('value').add_action(join)


power = (
    (OneOrMore(R(r'\d+(\.\d+)?') + R('×') + (R('10') + R('[-−–−]') + R(r'\d+') | R(r'^10[\-–−]?\d+$')))) |
    (R(r'\d+(\.\d+)?') + R('E', re.I) + Optional(R('[-−–−]')) + R(r'\d+')) |
    (OneOrMore(R(r'\d+(\.\d+)?·10') + R('[-−–−]') + R(r'\d+'))) |
    (R(r'\d+(\.\d+)?[Ee]?') + W('-') + R(r'\d+'))
).add_action(join)

gas_density_value = (power | range1 | value)('gas_density_value')

gas_density_cell = (OneOrMore(gas_density_value) + Optional(delims.hide()) + Optional(gas_density_units))('gas_density_cell')  # + Optional(gas_density_units)


'''5.气体粘度定义'''
gas_viscosity_title = (
        (R('[vv]iscosity') + W('of') + W('gas') + Optional(comma) + R('μ|μ') + W('g')) |
        (Optional(R('gas', re.I)) + R('viscosity|μg|ηg|viscidity', re.I) + Optional(comma) + Optional(R('μ') + W('g'))) |
        (Start() + R('μ|μ') + W('g')) |
        (Start() + R('μ|μ') + W('gas')) |
        (Start() + R('μ') + W('/') + R('[kK]g')) |
        (Start() + R('η|μ') + R('^[Gg]')) |
        (R('Dynamic') + R('viscosity') + Optional(comma) + R('μ')) |
        (R('gas', re.I) + Optional(R('dynamic')) + R('vis') + Optional(comma) + Optional(R('μ')) + Optional(R('[sg]')))
                       )
gas_viscosity_units = (
    (R('Pas')) |
    (R('Pa⋅s')) |
    (R('Pa', re.I) + Optional(stop) + Optional(W('.')) + R('s')) |
    (R('kg') + W('/') + W('m') + Optional(W('-') | W('/')) + W('s')) |
    (R('kg') + W('/') + R(r'm.?s?') + Optional(W('-') | W('.')) + Optional(W('s'))) |
    (R('Ns?') + Optional(R('s')) + W('/') + R('m2?') + Optional(W('2'))) |
    (W('kg') + W('m') + W('−') + W('1'))
)('gas_viscosity_units').add_action(merge)

gas_viscosity_heading = (OneOrMore(gas_viscosity_title.hide()) + Optional(delims.hide()) + Optional(gas_viscosity_units))('gas_viscosity_heading')

joined_range = R(r'^[\+\-–−]?\d+(\.\\d+)?(\(\d\))?[\-––-−~∼˜]\d+(\.\d+)?(\(\d\))?$')('value').add_action(join)

spaced_range = (R(r'^[\+\-–−]?\d+(\.d+)?(\(\d\))?$') + Optional(gas_viscosity_units).hide() + (R(r'^[\-±–−~∼˜]$') + R(r'^[\+\-–−]?\d+(\.\d+)?(\(\d\))?$') | R(r'^[\+\-–−]\d+(\.\d+)?(\(\d\))?$')))('value').add_action(join)

to_range = (ZeroOrMore(R(r'^[\+\-–−]?\d+(\.\d+)?(\(\d\))?$') + Optional(gas_viscosity_units).hide()) + Optional(I('to')) + R(r'^[\+\-–−]?\d+(\.\d+)?(\(\d\))?$'))('value').add_action(join)

to_range2 = ((R(r'^[\+\-–−]?\d+(\.\d+)?(\(\d\))?$') + I('<') + Optional(W('dp'))) + I('<') + R(r'^[\+\-–−]?\d+(\.\d+)?(\(\d\))?$'))('value').add_action(join)

and_range = (OneOrMore(R(r'^[\+\-–−]?\d+(\.\d+)?(\(\d\))?$') + Optional(gas_viscosity_units).hide() + Optional(comma))
             + Optional(I('and') | comma).hide() + R(r'^[\+\-–−]?\d+(\.\d+)?(\(\d\))?$'))('value').add_action(join)

range1 = (Optional(R(r'^[\-–−]$')) + (and_range | to_range2 | to_range | spaced_range | joined_range)).add_action(join)

value = (Optional(R(r'^[\-–−]$')) + Optional(R(r'^[~∼˜\<\>\≤\≥]$')) + Optional(R(r'^[\-\–\–\−±∓⨤⨦±]$'))
         + R(r'^[\+\-–−]?\d+(\.\d+)?(\(\d\))?$') + Optional(R(r'^[\-\–\–\−±∓⨤⨦±]$'))
         + ZeroOrMore(R(r'^[\+\-–−]?\d+(\.\d+)?(\(\d\))?$'))
         )('value').add_action(join)

power = (
    (OneOrMore(R(r'\d+(\.\d+)?') + R('×') + (R('10') + R('[-−–−]') + R(r'\d+') | R(r'^10[\-–−]?\d+$')))) |
    (R(r'\d+(\.\d+)?E?') + Optional(R('E', re.I)) + Optional(R('[-−–−+]')) + R(r'\d+')) |
    (OneOrMore(R(r'\d+(\.\d+)?·10') + R('[-−–−]') + R(r'\d+'))) |
    (R(r'\d+(\.\d+)?[Ee]?') + W('-') + R(r'\d+'))
).add_action(join)

gas_viscosity_value = (power | range1 | value)('gas_viscosity_value')

gas_viscosity_cell = (OneOrMore(gas_viscosity_value) + Optional(delims.hide()) + Optional(gas_viscosity_units))('gas_viscosity_cell')
# + Optional(gas_viscosity_units)

'''6.最小流化速度定义'''
Umf_title = (
    (Start() + R('^Min', re.I) + R('fluidiz') + R('vel') + End()) |
    (Start() + R('^Min', re.I) + R('fluidiz') + R('vel') + R('^[UV]mf$', re.I)) |
    (R('^[Mm]in', re.I) + R('fluidiz') + (R('vel') + W(',') | W('(') | W('['))
     + Optional(R('exp')) + Optional(stop) + Optional(W(')') | W(','))
     + Optional(R('μ$', re.I)) + Optional(R('[vU]?mf$', re.I)) + Optional(R('[vU]?min$', re.I))
     + Optional(W('at') + R(r'\d+') + W('°') + W('C') + Optional(W(')')))) |
    (Start() + Optional(R('[Ee]xperimental|Fluidi')) + R('^[Uu]mf|minimum') + Optional(R('[Ff]luidiz')) + R('[Vv]el')) |
    (Start() + R('^[Mm]in') + Optional(stop) + Optional(R('[Ff]luid')) + Optional(stop) + R('[Vv]el')) |
    (R('velocity') + Optional(delims) + R('^[UV]mf$', re.I)) |
    (R('velocity') + Optional(delims) + R('^[UV]', re.I) + R('^mf$', re.I)) |
    (R('^[uv]mf', re.I) + W('(') + OneOrMore(T('NNP') | T('JJ')) + OneOrMore(T('NN')) + OneOrMore(T('CD'))) |
    (R('^[uv]mf', re.I) + Optional(W(',')) + Optional(W('(')) + Optional(W('at')) + R(r'\d+') + W('°') + W('C') + Optional(W(')'))) |
    (R('[Ee]xperimental|[Tt]heoritical|Conventional') + R('^[VU]mf', re.I)) |
    (R(r'[^⋅*%+-−/-atabove]') + R('^[UV]mf$', re.I) + R('[^=]')) |
    (Start() + R('^[VU]mf$', re.I) + comma) |
    (Start() + R('^[VU]mf', re.I) + End()) |
    (Start() + R('^[VU]mf$', re.I) + W('(')) |
    (Start() + R('^[VU]mf$', re.I) + W('[')) |
    (Start() + R('^[VU]mf$', re.I) + W('/')) |
    (Start() + R('^[VU]mf$', re.I) + W('m') + W('/') + W('s')) |
    (Start() + R('^[UV]mf$', re.I) + Optional(delims) + R('[^=+orstnmd]|exp|cal')) |
    (R('Superficial') + R('vel') + W('at') + R('min') + Optional(R('fluid')) + Optional(W('/'))) |
    (Start() + R('^[VU]mf[*⁎]$', re.I))  # start 表示匹配开始的字符
)

Umf_units = (
        (R('[cm]?m') + W('s') + T(':') + R('1')) |  # 分词标注词性过程中的问题('−', ':')
        (R('^[cm]?m') + R(r's[\-–−]?1?$')) |
        (R('^[cm]?m') + Optional(stop) + R(r's[\-–−]?1?$')) |
        (R('[mc]?m·?s') + R(r'[-–−]') + R('1')) |
        (R('^[cm]?m') + W('/') + R('s|sec')) |
        (R('^[cm]?m') + W('/') + T('NNS')) |
        (R('[cm]?m') + W('s') + R(r'[-–−]') + R('1')) |
        (R('cm') + R('N') + W('/') + R('s|sec'))
)('Umf_units').add_action(merge)

Umf_heading = (
     # (Umf_title.hide() + Optional(delims.hide()) + Optional(Umf_units) + Optional(rbrct)) |
     (Umf_title.hide() + Optional(delims.hide()) + Optional(Umf_units) + Optional(rbrct) + Not(W('Standard')))
)('Umf_heading')


joined_range = R(r'^[\+\-–−]?\d+(\.\\d+)?(\(\d\))?[\-––-−~∼˜]\d+(\.\d+)?(\(\d\))?$')('value').add_action(join)

spaced_range = (R(r'^[\+\-–−]?\d+(\.d+)?(\(\d\))?$') + Optional(Umf_units).hide() + (R(r'^[\-––-−~∼˜±]$') + R(r'^[\+\-–−]?\d+(\.\d+)?(\(\d\))?$') | R(r'^[\+\-–−]\d+(\.\d+)?(\(\d\))?$')))('value').add_action(join)

to_range = (ZeroOrMore(R(r'^[\+\-–−]?\d+(\.\d+)?(\(\d\))?$') + Optional(Umf_units).hide()) + Optional(I('to')) + R(r'^[\+\-–−]?\d+(\.\d+)?(\(\d\))?$'))('value').add_action(join)

to_range2 = ((R(r'^[\+\-–−]?\d+(\.\d+)?(\(\d\))?$') + I('<') + Optional(W('dp'))) + I('<') + R(r'^[\+\-–−]?\d+(\.\d+)?(\(\d\))?$'))('value').add_action(join)

an_range = (OneOrMore(R(r'^[\+\-–−]?\d+(\.\d+)?(\(\d\))?$') + Optional(Umf_units).hide() + Optional(comma))
             + Optional(I('and') | comma).hide() + R(r'^[\-––-−~∼˜]?\d+(\.\d+)?(\(\d\))?$')
              )('value').add_action(join)

and_range = (R(r'^[\+\-–−]?\d+(\.d+)?(\(\d\))?$') +
             OneOrMore(R(r'^[\+\-––-−~∼˜±]?\d+(\.\d+)?(\(\d\))?$') + Optional(Umf_units).hide() + Optional(comma)))('value').add_action(join)

range1 = (an_range | and_range | spaced_range | joined_range | to_range2 | to_range).add_action(join)

value = (Optional(R(r'^[\-–−]$')) + Optional(R(r'^[~∼˜\<\>\≤\≥]$')) + Optional(R(r'^[\-\–\–\−±∓⨤⨦±]$'))
         + R(r'^[\+\-–−]?\d+(\.\d+)?(\(\d\))?$') + Optional(R(r'^[\-\–\–\−±∓⨤⨦±]$'))
         + ZeroOrMore(R(r'^[\+\-–−]?\d+(\.\d+)?(\(\d\))?$'))
         )('value').add_action(join)

power = (
    (OneOrMore(R(r'\d+(\.\d+)?') + R('×|·') + (R('10') + R('[-−–−]') + R(r'\d+') | R(r'^10[\-–−]?\d+$')))) |
    (OneOrMore(R(r'\d+(\.\d+)?·10') + R('[-−–−]') + R(r'\d+'))) |
    (R(r'\d+(\.\d+)?') + R('E', re.I) + Optional(R('[-−–−]')) + R(r'\d+')) |
    (R(r'\d+(\.\d+)?[Ee]?') + W('-') + R(r'\d+'))
).add_action(join)

Umf_value = (power | range1 | value | value1)('Umf_value')

Umf_cell = (OneOrMore(Umf_value) + Optional(delims.hide()) + Optional(Umf_units))('Umf_cell')  #

subject_phrase = ((I('of') | I('for')) + particle_label)('subject_phrase')

'''7. 操作温度'''

Temp_title = (
        (R('Temperature') + Optional(comma) + W('T')) |
        # (R('^[Tt]emperature|^T$') + Not(Any())) |
        (R('Bed') + R('temperature')) |
        (R('[pP]article') + R('temperature')) |
        (R('T') + W('bed')) |
        (R('Tbed')) |
        (Start() + R('^T$')) |
        (Start() + R('^[Tt]emperature$')+ Not(Any())) |
        (T('^θ$'))
)

Temp_units = ((W('°') + R('[CFK]')) | R('^K$'))('Temp_units').add_action(join)

Temp_headings = (OneOrMore(Temp_title.hide()) + Optional(delims.hide()) + Optional(Temp_units))('Temp_heading')

Temp_value = (Optional(R(r'^[\-–−]$')) + Optional(R(r'^[~∼˜\<\>\≤\≥]$')) + Optional(R(r'^[\-\–\–\−±∓⨤⨦±]$'))
         + R(r'^[\+\-–−]?\d+(\.\d+)?(\(\d\))?$') + Optional(R(r'^[\-\–\–\−±∓⨤⨦±]$'))
         + ZeroOrMore(R(r'^[\+\-–−]?\d+(\.\d+)?(\(\d\))?$'))
         )('Temp_value').add_action(join)

Temp_cell = (OneOrMore(Temp_value) + Optional(delims.hide()) + Optional(Temp_units))('Temp_cell')

'''7. 操作温度'''
temp_range = (Optional(R(r'^[\-–−]$')) + (R(r'^[\+\-–−]?\d+(\.\d+)?[\-–−]\d+(\.\d+)?$') | (R(r'^[\+\-–−]?\d+(\.\d+)?$') + R(r'^[\-–−]$') + R(r'^[\+\-–−]?\d+(\.\d+)?$'))))('temperature').add_action(merge)

temp_value = (Optional(R(r'^[\-–−]$')) + Optional(R(r'^[~∼˜\<\>\≤\≥]$')) + Optional(R(r'^[\-\–\–\−±∓⨤⨦±]$'))
         + R(r'^[\+\-–−]?\d+(\.\d+)?(\(\d\))?$') + Optional(R(r'^[\-\–\–\−±∓⨤⨦±]$')) + Optional(I('and'))
         + ZeroOrMore(R(r'^[\+\-–−]?\d+(\.\d+)?(\(\d\))?$'))
         )('temperature').add_action(join)

temp_word = (I('room') + R('^temp(erature)?$') | R(r'^r\.?t\.?$', re.I))('temperature').add_action(merge)

temp = (temp_range | temp_value | temp_word)('value')

temp_units = ((W('°') + R('[CFK]')) | R('^K$'))('units').add_action(merge)

temp_with_units = (temp + temp_units)('temp')

temp_phrase = (Optional(W('and')) + Optional(I('at')) + temp_with_units)('temp_phrase')

'''8. 操作压力'''
Press_title = (
        (R('Pressure', re.I) + Optional(comma) + R('^[Pp]')) |
        (R('Operating') + R('pressure') + (W('(') | W('['))) |
        (Start() + R('pressure|^p$', re.I) + Not(W('drop') | W('fluctuations') | W('/')))
)

Press_units = (
        R('[^[km]?Pa$', re.I) |
        R('^m?bara?$') + Not(I('/')) |
        R('^atm$')
)('Press_units').add_action(merge)

Press_headings = (OneOrMore(Press_title.hide()) + Optional(delims.hide()) + Optional(Press_units))('Press_heading')


Press_value = (Optional(R(r'^[\-–−]$')) + Optional(R(r'^[~∼˜\<\>\≤\≥]$')) + Optional(R(r'^[\-\–\–\−±∓⨤⨦±]$'))
         + R(r'^[\+\-–−]?\d+(\.\d+)?(\(\d\))?$') + Optional(R(r'^[\-\–\–\−±∓⨤⨦±]$'))
         + ZeroOrMore(R(r'^[\+\-–−]?\d+(\.\d+)?(\(\d\))?$'))
         )('Press_value').add_action(join)

Press_cell = (OneOrMore(Press_value) + Optional(delims.hide()) + Optional(Press_units))('Press_cell')

'''8. 操作压力'''
press_range = (Optional(R(r'^[\-–−]$')) + (R(r'^[\+\-–−]?\d+(\.\d+)?[\-–−]\d+(\.\d+)?$') | (R(r'^[\+\-–−]?\d+(\.\d+)?$') + R(r'^[\-–−]$') + R(r'^[\+\-–−]?\d+(\.\d+)?$'))))('pressure').add_action(merge)


press_value = (Optional(R(r'^[\-–−]$')) + Optional(R(r'^[~∼˜\<\>\≤\≥]$')) + Optional(R(r'^[\-\–\–\−±∓⨤⨦±]$'))
         + R(r'^[\+\-–−]?\d+(\.\d+)?(\(\d\))?$') + Optional(R(r'^[\-\–\–\−±∓⨤⨦±]$'))
         + ZeroOrMore(R(r'^[\+\-–−]?\d+(\.\d+)?(\(\d\))?$'))
         )('press_value').add_action(join)

press_word = (I('room') + R('^condition?$') | R(r'^r\.?t\.?$', re.I))('pressure').add_action(merge)

press = (press_range | press_value)('value')

press_units = (((R('^[km]?Pa$', re.I) | R('^bar$')) + Not(I('/')))('units')).add_action(merge)

press_with_units = (press + press_units)('press')

press_phrase = (Optional(W('and')) + Optional(I('at')) + press_with_units)('press_phrase')


'''9.颗粒性质出现在标题中'''
diameter_range = (
        Optional(R(r'^[\-–−]$')) +
        (R(r'^[\+\-–−]?\d+(\.\d+)?$') + R(r'^[\-–−]$') + R(r'^[\+\-–−]?\d+(\.\d+)?$')) |
        R(r'^[\+\-–−]?\d+(\.\d+)?[\-–−]\d+(\.\d+)?$')
)('diameter').add_action(merge)

diameter_value = (Optional(R(r'^[\-–−]$')) + R(r'^[\+\-–−]?\d+(\.\d+)?$') + Optional(W('±') + R(r'^\d+(\.\d+)?$')))('diameter').add_action(merge)

# diameter_word = (I('of') | I('for') | I('with') |I('using'))('diameter').add_action(merge)

diameter = (diameter_range | diameter_value)('value') #  | diameter_word

diameter_units = ((R('^[µμcm]m$') + Not(W('/'))) | (R('μ|μ') + W('m')))('units').add_action(merge)

diameter_with_units = (diameter + diameter_units)('diam')

diameter_phrase = (Not(W('height')) + Optional(W('of')) + Optional(I('with')) + Optional(W('=')) + diameter_with_units)('diam_phrase')

density_range = (
        Optional(R(r'^[\-–−]$')) +
        (R(r'^[\+\-–−]?\d+(\.\d+)?$') + R(r'^[\-–−]$') + R(r'^[\+\-–−]?\d+(\.\d+)?$')) |
        R(r'^[\+\-–−]?\d+(\.\d+)?[\-–−]\d+(\.\d+)?$')
)('density').add_action(merge)

density_value = (Optional(R(r'^[\-–−]$')) + R(r'^[\+\-–−]?\d+(\.\d+)?$') + Optional(W('±') + R(r'^\d+(\.\d+)?$')))('density').add_action(merge)

# density_word = (I('was') + Optional(I('approximately')))('density').add_action(merge)

density = (density_range | density_value)('value')

density_units = (R('[kK]?g$') + W('/') + W('c?m'))('units').add_action(merge)

density_with_units = (density + density_units)('dens')

density_phrase = (Optional(W('of')) + Optional(I('with')) + Optional(W('=')) + density_with_units)('dens_phrase')

caption_context = Group(subject_phrase | press_phrase | temp_phrase | diameter_phrase | density_phrase)('caption_context')


'''10.单位自成一列'''
unit_heading = (R('^units?$|^comments?$', re.I))('unit_heading')

unit_particle_diameter_cell = ((R('^[µμcm]?m$') + Not(W('/'))) |
                          (R('μ|μ') + W('m')))('particle_diameter_units').add_action(merge)('unit_particle_diameter_cell')

unit_particle_density_cell = ((R('[Kk]?g') + R(r'[c]?m[\-–−]?3?')) |
                         (R('[Kk]?g') + W('/') + R('c?m')))('particle_density_units').add_action(merge)('unit_particle_density_cell')

unit_gas_density_cell = (
        (R('[k]?g') + R(r'[c]?m[\-–−]3')) |
        (R('[k]?g')+W('/')+R('[c]?m'))
                         )('gas_density_units').add_action(merge)('unit_gas_density_cell')

unit_gas_viscosity_cell = (R('Pa') + Optional(stop) + Optional(W('.')) + R('s'))('gas_viscosity_units').add_action(merge)('unit_gas_viscosity_cell')

unit_velocity_cell = ((R('^[cm]?m') + R(r's[\-–−]?1?$')) | (R('^[cm]?m') + W('/') + W('s')))('Umf_units').add_action(merge)('unit_velocity_cell')


class CompoundHeadingParser(BaseParser):
    """"""
    root = compound_heading

    def interpret(self, result, start, end):
        """"""
        yield Compound()


class CompoundCellParser(BaseParser):
    """"""
    root = compound_cell

    def interpret(self, result, start, end):
        for cem_el in result.xpath('./material'):
            c = Compound(
                names=cem_el.xpath('./name/text()'),
                labels=cem_el.xpath('./label/text()')
            )
            yield c


class ParticleDiameterHeadingParser(BaseParser):

    root = particle_diameter_heading

    def interpret(self, result, start, end):
        """"""
        c = Compound()
        pdd = ParticleDiameter(
            units=first(result.xpath('./particle_diameter_units/text()'))
        )
        # print(pdd.units)
        # if pdd.units: # 如果加if语句的话，当title中没有单位时，就会出现不能识别headingParser的现象
        c.particle_diameter.append(pdd)
        yield c


class ParticleDiameterCellParser(BaseParser):

    root = table_particle_diameter_cell

    def interpret(self, result, start, end):
        c = Compound()
        pdd = ParticleDiameter(
            value=first(result.xpath('./particle_diameter_value/text()')),
            units=first(result.xpath('./particle_diameter_units/text()'))
        )
        # print(pdd.value)
        if pdd.value:
            c.particle_diameter.append(pdd)
            yield c


class ParticleDensityHeadingParser(BaseParser):

    root = particle_density_heading

    def interpret(self, result, start, end):
        """"""
        c = Compound()
        pdd_units = ParticleDensity(
            units=first(result.xpath('./particle_density_units/text()'))
        )
        # print(pdd_units.units)
        # if pdd_units.units: # 如果加if语句的话，当title中没有单位时，就会出现不能识别headingParser的现象
        c.particle_density.append(pdd_units)
        yield c


class ParticleDensityCellParser(BaseParser):

    root = particle_density_cell

    def interpret(self, result, start, end):
        """"""
        c = Compound()
        # print(c)
        pd_value = ParticleDensity(
            value=first(result.xpath('./particle_density_value/text()')),
            units=first(result.xpath('./particle_density_units/text()'))
        )
        # print(pd_value.value)
        if pd_value.value:
            c.particle_density.append(pd_value)
            yield c


class ParticleSphericityHeadingParser(BaseParser):

    root = particle_sphericity_heading

    def interpret(self, result, start, end):
        """"""
        yield Compound()


class ParticleSphericityCellParser(BaseParser):

    root = particle_sphericity_cell

    def interpret(self, result, start, end):
        """"""
        # print(result.text)
        # print(result.xpath('./text()'))
        c = Compound()
        # print(c)
        ps_value = Sphericity(
            value=first(result.xpath('./text()')),
        )
        # print(ps_value.value)
        if ps_value.value:
            c.particle_sphericity.append(ps_value)
            yield c


class BedVoidageHeadingParser(BaseParser):

    root = bed_voidage_heading

    def interpret(self, result, start, end):
        """"""
        yield Compound()


class BedVoidageCellParser(BaseParser):

    root = bed_voidage_cell

    def interpret(self, result, start, end):
        """"""
        # print(result.text)
        # print(result.xpath('./text()'))
        c = Compound()
        # print(c)
        bv_value = BedVoidage(
            value=first(result.xpath('./text()')),
        )
        # print(ps_value.value)
        if bv_value.value:
            c.bed_voidage.append(bv_value)
            yield c


class GasDensityHeadingParser(BaseParser):

    root = gas_density_heading

    def interpret(self, result, start, end):
        """"""
        c = Compound()
        gd_units = GasDensity(
            units=first(result.xpath('./gas_density_units/text()'))
        )
        # print(gd_units.units)
        # if gd_units.units: # 如果加if语句的话，当title中没有单位时，就会出现不能识别headingParser的现象
        c.gas_density.append(gd_units)
        yield c


class GasDensityCellParser(BaseParser):

    root = gas_density_cell

    def interpret(self, result, start, end):
        """"""
        c = Compound()
        gd = GasDensity(
            value=first(result.xpath('./gas_density_value/text()')),
            units=first(result.xpath('./gas_density_units/text()'))
        )
        if gd.value:
            c.gas_density.append(gd)
            yield c


class GasViscosityHeadingParser(BaseParser):

    root = gas_viscosity_heading

    def interpret(self, result, start, end):
        """"""

        c = Compound()
        gv_units = GasViscosity(
            units=first(result.xpath('./gas_viscosity_units/text()'))
        )
        # print(gv_units.units)
        # if gv_units.units: # 如果加if语句的话，当title中没有单位时，就会出现不能识别headingParser的现象
        c.gas_viscosity.append(gv_units)
        yield c


class GasViscosityCellParser(BaseParser):

    root = gas_viscosity_cell

    def interpret(self, result, start, end):
        """"""
        c = Compound()
        gv = GasViscosity(
            value=first(result.xpath('./gas_viscosity_value/text()')),
            units=first(result.xpath('./gas_viscosity_units/text()'))
        )
        if gv.value:
            c.gas_viscosity.append(gv)
            yield c


class VelocityHeadingParser(BaseParser):

    root = Umf_heading

    def interpret(self, result, start, end):
        # print(result)
        """"""
        c = Compound()
        # print(end)
        # print(result.xpath('./Umf_units/text()'))
        v_units = Velocity(
            units=first(result.xpath('./Umf_units/text()'))
        )
        # print(v_units.units)
        # if v_units.units: # 如果加if语句的话，当title中没有单位时，就会出现不能识别headingParser的现象
        c.Umf.append(v_units)
        yield c


class VelocityCellParser(BaseParser):

    root = Umf_cell

    def interpret(self, result, start, end):
        """"""
        c = Compound()
        v = Velocity(
            value=first(result.xpath('./Umf_value/text()')),
            units=first(result.xpath('./Umf_units/text()'))
        )
        # print(v.value, v.units)
        if v.value:
            c.Umf.append(v)
            yield c


class TempHeadingParser(BaseParser):

    root = Temp_headings

    def interpret(self, result, start, end):
        """"""
        c = Compound()
        TT = TabelTemp(
            units=first(result.xpath('./Temp_units/text()'))
        )
        c.Table_Temp.append(TT)
        yield c


class TempCellParser(BaseParser):

    root = Temp_cell

    def interpret(self, result, start, end):
        c = Compound()
        TT = TabelTemp(
            value=first(result.xpath('./Temp_value/text()')),
            units=first(result.xpath('./Temp_units/text()'))
        )
        # print(pdd.value)
        if TT.value:
            c.Table_Temp.append(TT)
            yield c


class PressHeadingParser(BaseParser):

    root = Press_headings

    def interpret(self, result, start, end):
        """"""
        c = Compound()
        TP = TabelPress(
            units=first(result.xpath('./Press_units/text()'))
        )
        c.Table_Press.append(TP)
        yield c


class PressCellParser(BaseParser):

    root = Press_cell

    def interpret(self, result, start, end):
        c = Compound()
        TP = TabelPress(
            value=first(result.xpath('./Press_value/text()')),
            units=first(result.xpath('./Press_units/text()'))
        )
        if TP.value:
            c.Table_Press.append(TP)
            yield c


class TempInHeadingParser(BaseParser):
    """"""
    root = temp_with_units
    # print(root)

    def interpret(self, result, start, end):
        """"""
        c = Compound()
        # print(first(result.xpath('./value/text()')))
        context = {
            'temperature': first(result.xpath('./value/text()')),
            'temperature_units': first(result.xpath('./units/text()'))
        }
        # print(context)
        c.Umf = [Velocity(**context)]
        yield c


class PressInHeadingParser(BaseParser):
    """"""
    root = press_with_units
    # print(root)

    def interpret(self, result, start, end):
        """"""
        c = Compound()
        # print(first(result.xpath('./value/text()')))
        context = {
            'pressure': first(result.xpath('./value/text()')),
            'pressure_units': first(result.xpath('./units/text()'))
        }
        # print(context)
        c.Umf = [Velocity(**context)]
        yield c


class CaptionContextParser(BaseParser):
    """"""
    root = caption_context

    def __init__(self):
        pass

    def interpret(self, result, start, end):

        # print()
        name = first(result.xpath('./subject_phrase/name/text()'))

        c = Compound(names=[name]) if name else Compound()
        context = {}

        temp = first(result.xpath('./temp_phrase'))

        if temp is not None:
            context['temperature'] = first(temp.xpath('./temp/value/text()'))
            context['temperature_units'] = first(temp.xpath('./temp/units/text()'))

        press = first(result.xpath('./press_phrase'))

        # print(context)

        if press is not None:
            context['pressure'] = first(press.xpath('./press/value/text()'))
            context['pressure_units'] = first(press.xpath('./press/units/text()'))
        # print(context)

        diam = first(result.xpath('./diam_phrase'))

        # print(diameter)

        if diam is not None:
            context['diameter'] = first(diam.xpath('./diam/value/text()'))
            context['diameter_units'] = first(diam.xpath('./diam/units/text()'))

        if context:
            c.Umf = [Velocity(**context)]

        if c.serialize():
            yield c
