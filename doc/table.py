# -*- coding: utf-8 -*-
"""
chemdataextractor.doc.table
~~~~~~~~~~~~~~~~~~~~~~~~~~~

Table document elements.

"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals
import logging
from collections import defaultdict

from ..model import Compound, ModelList
# from ..parse.table import CompoundHeadingParser, CompoundCellParser, UvvisAbsHeadingParser, UvvisAbsCellParser, \
#     QuantumYieldHeadingParser, QuantumYieldCellParser, UvvisEmiHeadingParser, UvvisEmiCellParser, ExtinctionCellParser, \
#     ExtinctionHeadingParser, FluorescenceLifetimeHeadingParser, FluorescenceLifetimeCellParser, \
#     ElectrochemicalPotentialHeadingParser, ElectrochemicalPotentialCellParser, IrHeadingParser, IrCellParser, \
#     SolventCellParser, SolventHeadingParser, SolventInHeadingParser, UvvisAbsEmiQuantumYieldHeadingParser, \
#     UvvisAbsEmiQuantumYieldCellParser, MeltingPointHeadingParser, MeltingPointCellParser, GlassTransitionHeadingParser, GlassTransitionCellParser, TempInHeadingParser, \
#     UvvisAbsDisallowedHeadingParser, UvvisEmiQuantumYieldHeadingParser, UvvisEmiQuantumYieldCellParser,PressInHeadingParser
#
from ..parse.table import CompoundHeadingParser, CompoundCellParser, ParticleDiameterHeadingParser, ParticleDiameterCellParser, ParticleDensityHeadingParser, \
    ParticleDensityCellParser, ParticleSphericityHeadingParser, ParticleSphericityCellParser, GasViscosityHeadingParser, GasDensityHeadingParser, \
    BedVoidageHeadingParser, BedVoidageCellParser, GasViscosityCellParser, GasDensityCellParser, VelocityHeadingParser,VelocityCellParser, TempInHeadingParser, \
    PressInHeadingParser, TempHeadingParser, TempCellParser, PressHeadingParser, PressCellParser

# TODO: Sort out the above import... import module instead
from ..nlp.tag import NoneTagger
from ..nlp.tokenize import FineWordTokenizer
from ..utils import memoized_property
from .element import CaptionedElement
from .text import Sentence
from ..parse import R, W
import re

log = logging.getLogger(__name__)


class Table(CaptionedElement):

    #: Table cell parsers
    parsers = [

        (TempInHeadingParser(),),
        (CompoundHeadingParser(), CompoundCellParser()),
        (ParticleDiameterHeadingParser(), ParticleDiameterCellParser()),
        (ParticleDensityHeadingParser(), ParticleDensityCellParser()),
        (ParticleSphericityHeadingParser(), ParticleSphericityCellParser()),
        (BedVoidageHeadingParser(), BedVoidageCellParser()),
        (GasDensityHeadingParser(), GasDensityCellParser()),
        (GasViscosityHeadingParser(), GasViscosityCellParser()),
        (VelocityHeadingParser(), VelocityCellParser()),
        (TempHeadingParser(), TempCellParser()),
        (PressHeadingParser(), PressCellParser()),
        (PressInHeadingParser(),)
    ]

    def __init__(self, caption, label=None, headings=None, rows=None, footnotes=None, **kwargs):
        super(Table, self).__init__(caption=caption, label=label, **kwargs)
        # print(caption)
        # print(headings)
        self.headings = headings if headings is not None else []  # list(list(Cell))
        # print(self.headings)
        self.rows = rows if rows is not None else []  # list(list(Cell))
        # print(footnotes)
        self.footnotes = footnotes if footnotes is not None else []
        # print(footnotes)

    @property
    def document(self):
        # print(self)
        return self._document

    @document.setter
    def document(self, document):
        # print(document)
        self._document = document
        # print(self._document)
        self.caption.document = document
        for row in self.headings:
            # print(row)
            for cell in row:
                cell.document = document
        for row in self.rows:
            for cell in row:
                cell.document = document

    def serialize(self):
        """Convert Table element to python dictionary."""
        data = {
            'type': self.__class__.__name__,
            'caption': self.caption.serialize(),
            'headings': [[cell.serialize() for cell in hrow] for hrow in self.headings],
            'rows': [[cell.serialize() for cell in row] for row in self.rows],
            'footnotes': self.footnote.serialize(),  # 20200916 add
        }
        # print(data)
        return data

    def _repr_html_(self):
        html_lines = ['<table class="table">']
        html_lines.append(self.caption._repr_html_  ())
        html_lines.append('<thead>')
        # print(html_lines)
        for hrow in self.headings:
            html_lines.append('<tr>')
            # print(html_lines)
            for cell in hrow:
                html_lines.append('<th>' + cell.text + '</th>')
        html_lines.append('</thead>')
        html_lines.append('<tbody>')
        for row in self.rows:
            html_lines.append('<tr>')
            for cell in row:
                html_lines.append('<td>' + cell.text + '</td>')
        html_lines.append('</tbody>')
        html_lines.append('</table>')
        return '\n'.join(html_lines)

    @property
    def records(self):
        """Chemical records that have been parsed from the table."""
        '''1. 分析表格的标题'''
        # print(self)
        caption_records = self.caption.records
        # print(caption_records)
        # Parse headers to extract contextual data and determine value parser for the column
        value_parsers = {}
        header_compounds = defaultdict(list)
        row_fisrt_compounds = defaultdict(list)
        table_records = ModelList()
        seen_compound_col = False
        log.debug('Parsing table headers')

        '''2. 分析表格第一行'''
        # print(*self.headings)
        # 暂时根据第一行第一列的关键词(key_words,key_words_1)来区分两种表格,这种方法有很大问题
        # 可以根据第一行是否由关键字（如Umf）来判断表格形式
        # key_words = re.compile('variable|parameter|propert|item|specification'
        #                        '|condition|talyst|symbol|haracter|significa', re.I)
        # key_words_1 = re.compile('[Ss]and|I|[vV]alues?|Calcium|Bed|Jetsam|conditions?|Small|FCC|GB|HDPE|Case|reactor')
        key_word = re.compile('^min|[vu]mf', re.I)
        key_word1 = re.compile('den|^ρ', re.I)
        key_word2 = re.compile('diam|^dp?', re.I)
        # if self.headings != [] and key_words.search(str(self.headings[0][0])) == None \
        #         and len(self.headings[0]) > 1 and key_words_1.search(str(self.headings[0][1])) == None:
        judge = False
        judge1 = False
        judge2 = False
        if self.headings != []:
            for i in range(len(self.headings[0])):
                # print(str(self.headings[0][i]))
                # print(key_word1.search(str(self.headings[0][i])))
                # print(key_word2.search(str(self.headings[0][i])))
                if key_word.search(str(self.headings[0][i])) != None:
                    judge = True
                elif key_word1.search(str(self.headings[0][i]))!= None:
                    judge1 = True
                elif key_word2.search(str(self.headings[0][i])) != None:
                    judge2 = True

        # print(self.headings)
        if judge or (judge1 and judge2):
            if len(self.headings) > 1:
                for i in range(len(self.headings)-1):
                    for j in range(len(self.headings[i])):
                        self.headings[i][j] = self.headings[i][j] + Cell(' ') + self.headings[i+1][j]

            # print(self.headings)
            for i, col_headings in enumerate(zip(*self.headings)):
                for parsers in self.parsers:
                    log.debug(parsers)
                    # print(parsers[0]) #nds of HeadingParser
                    heading_parser = parsers[0]
                    value_parser = parsers[1] if len(parsers) > 1 else None
                    disallowed_parser = parsers[2] if len(parsers) > 2 else None
                    allowed = False
                    disallowed = False
                    # print(col_headings)
                    for cell in col_headings:
                        # print(cell)
                        log.debug(cell.tagged_tokens)
                        results = list(heading_parser.parse(cell.tagged_tokens))
                        # print(cell.tagged_tokens)
                        # print(results)
                        if results:
                            allowed = True
                            log.debug('Heading column %s: Match %s: %s' % (
                                i, heading_parser.__class__.__name__, [c.serialize() for c in results]))
                        # Results from every parser are stored as header compounds
                        # print(header_compounds)
                        header_compounds[i].extend(results)
                        # print(header_compounds)
                        # Referenced footnote records are also stored
                        # print(self.footnotes)
                        for footnote in self.footnotes:
                            # print('%s - %s - %s' % (footnote.id, cell.references, footnote.id in cell.references))
                            if footnote.id in cell.references:
                                log.debug('Adding footnote %s to column %s: %s' % (
                                    footnote.id, i, [c.serialize() for c in footnote.records]))
                                # print('Footnote records: %s' % [c.to_primitive() for c in footnote.records])
                                header_compounds[i].extend(footnote.records)
                        # Check if the disallowed parser matches this cell
                        # print(header_compounds)
                        if disallowed_parser and list(disallowed_parser.parse(cell.tagged_tokens)):
                            log.debug('Column %s: Disallowed %s' % (i, heading_parser.__class__.__name__))
                            disallowed = True
                    # If heading parser matches and disallowed parser doesn't, store the value parser
                    # print(value_parser)
                    if allowed and not disallowed and value_parser and i not in value_parsers:
                        if isinstance(value_parser, CompoundCellParser):
                            # Only take the first compound col
                            if seen_compound_col:
                                continue
                            seen_compound_col = True
                        log.debug('Column %s: Value parser: %s' % (i, value_parser.__class__.__name__))
                        value_parsers[i] = value_parser
                        # Stop after value parser is assigned?


            # print(value_parsers)
            #  如何heading中存在parsers，则分析下面的表格内容
            if value_parsers:

                # If no CompoundCellParser() in value_parsers and value_parsers[0] == [] then set CompoundCellParser()
                if not seen_compound_col and 0 not in value_parsers:
                    log.debug('No compound column found in table, assuming first column')
                    value_parsers[0] = CompoundCellParser()

                for row in self.rows:
                    # print(row) # 代表第一列的数据
                    row_compound = Compound()
                    # Keep cell records that are contextual to merge at the end
                    contextual_cell_compounds = []
                    for i, cell in enumerate(row):
                        # print(i,cell)
                        # print(value_parsers)
                        log.debug(cell.tagged_tokens)
                        if i in value_parsers:
                            # print(cell.tagged_tokens)
                            results = list(value_parsers[i].parse(cell.tagged_tokens))
                            if results:
                                log.debug('Cell column %s: Match %s: %s' % (
                                i, value_parsers[i].__class__.__name__, [c.serialize() for c in results]))
                            # For each result, merge in values from elsewhere
                            for result in results:
                                # Merge each header_compounds[i]
                                for header_compound in header_compounds[i]:
                                    if header_compound.is_contextual:
                                        result.merge_contextual(header_compound)
                                # Merge footnote compounds
                                for footnote in self.footnotes:
                                    if footnote.id in cell.references:
                                        for footnote_compound in footnote.records:
                                            result.merge_contextual(footnote_compound)
                                if result.is_contextual:
                                    # Don't merge cell as a value compound if there are no values
                                    contextual_cell_compounds.append(result)
                                else:
                                    row_compound.merge(result)
                    # Merge contextual information from cells
                    for contextual_cell_compound in contextual_cell_compounds:
                        row_compound.merge_contextual(contextual_cell_compound)
                    # If no compound name/label, try take from previous row
                    if not row_compound.names and not row_compound.labels and table_records:
                        prev = table_records[-1]
                        row_compound.names = prev.names
                        row_compound.labels = prev.labels
                    # Merge contextual information from caption into the full row
                    for caption_compound in caption_records:
                        if caption_compound.is_contextual:
                            row_compound.merge_contextual(caption_compound)
                    # And also merge from any footnotes that are referenced from the caption
                    for footnote in self.footnotes:
                        if footnote.id in self.caption.references:
                            # print('Footnote records: %s' % [c.to_primitive() for c in footnote.records])
                            for fn_compound in footnote.records:
                                row_compound.merge_contextual(fn_compound)

                    log.debug(row_compound.serialize())
                    if row_compound.serialize():
                        table_records.append(row_compound)


        else:
            unit_table = re.compile('^unit$|^comments?$|description$', re.I)
            mm = 0
            # print(self.headings)
            for i, heading in enumerate(zip(*self.headings)):  # (*self.headings):
                # print(i, heading, len(heading))
                # print(str(heading[0]))
                if len(heading) == 1:
                    if unit_table.search(str(heading[0])) != None:
                        mm = i
                else:
                    if unit_table.search(str(heading[1])) != None:
                        mm = i
            # print(mm)  # 首先确定unit或者comment所在的列
            # print(self.rows)
            self.rows = self.rows + self.headings
            # print(self.rows)
            if mm != 0:
                for r in self.rows:
                    r[0] = r[0] + Cell(' ') + r[mm]  # 然后将unit或者comment所在的列与第一列合并
                    r.remove(r[mm])  # 将unit或者comment所在的列删除

                nn = len(self.rows[0])
                # print(self.rows[0])
                # print(nn)
                # print(self.rows)
                for r in self.rows:
                    for j in range(nn):
                        if j > 1:
                            # print(r[1])
                            r[1] = r[1] + Cell(' ') + r[j]
                for r in self.rows:
                    for j in range(nn):
                        if j > 1:
                            r.remove(r[2])  # 移除第二列后，第三列变成第二列，以此类推，后面的均自动变成第二列

            # print(self.rows)
            rows = ()
            for i, row in enumerate(zip(*self.rows)):
                if i == 0:
                    rows = row
            # print(list(rows))
            rows = list(rows)
            for i, row in enumerate(zip(rows)):
                # print(i, row)
                for parsers in self.parsers:
                    log.debug(parsers)
                    row_parser = parsers[0]
                    value_parser = parsers[1] if len(parsers) > 1 else None
                    disallowed_parser = parsers[2] if len(parsers) > 2 else None
                    allowed = False
                    disallowed = False
                    # print(row)
                    for cell in row:
                        # print(cell)
                        results = list(row_parser.parse(cell.tagged_tokens))
                        # print(cell.tagged_tokens)
                        # print(results)
                        if results:
                            allowed = True
                        row_fisrt_compounds[i].extend(results)
                        # print(row_fisrt_compounds)
                        for footnote in self.footnotes:
                            if footnote.id in cell.references:
                                row_fisrt_compounds[i].extend(footnote.records)
                        if disallowed_parser and list(disallowed_parser.parse(cell.tagged_tokens)):
                            disallowed = True
                    if allowed and not disallowed and value_parser and i not in value_parsers:
                        if isinstance(value_parser, CompoundCellParser):
                            if seen_compound_col:
                                continue
                            seen_compound_col = True
                        value_parsers[i] = value_parser
            # print(value_parsers)

            # print(value_parsers)
            if value_parsers:
                if not seen_compound_col and 0 not in value_parsers:
                    value_parsers[0] = CompoundCellParser()
                # print(value_parsers)
                temp_row = []
                for i, row in enumerate(zip(*self.rows)):
                    if i != 0:
                        temp_row.append(row)
                temp_row = list(temp_row)
                rows_temp = ()
                # print(temp_row)
                for row in temp_row:
                    row_compound = Compound()
                    contextual_cell_compounds = []
                    # print(row)
                    for i, cell in enumerate(row):
                        # print(i, cell.tokens)
                        # print(value_parsers)
                        if i in value_parsers:
                            # print(value_parsers[i])                    
                            results = list(value_parsers[i].parse(cell.tagged_tokens))
                            # print(cell.tagged_tokens)
                            # print(results)
                            if results:
                                log.debug('Cell column %s: Match %s: %s' % (
                                    i, value_parsers[i].__class__.__name__, [c.serialize() for c in results]))
                            for result in results:
                                for row_fisrt_compound in row_fisrt_compounds[i]:
                                    if row_fisrt_compound.is_contextual:
                                        result.merge_contextual(row_fisrt_compound)
                                # print(result)
                                for footnote in self.footnotes:
                                    if footnote.id in cell.references:
                                        for footnote_compound in footnote.records:
                                            result.merge_contextual(footnote_compound)
                                if result.is_contextual:
                                    contextual_cell_compounds.append(result)
                                else:
                                    row_compound.merge(result)
                    # print(row_compound)
                    # print(contextual_cell_compounds)
                    for contextual_cell_compound in contextual_cell_compounds:
                        row_compound.merge_contextual(contextual_cell_compound)

                    if not row_compound.names and not row_compound.labels and table_records:
                        prev = table_records[-1]
                        row_compound.nes = prev.names
                        row_compound.labels = prev.labels
                    # print(row_compound)
                    # Merge contextual information from caption into the full row
                    for caption_compound in caption_records:
                        if caption_compound.is_contextual:
                            row_compound.merge_contextual(caption_compound)
                    # And also merge from any footnotes that are referenced from the caption
                    for footnote in self.footnotes:
                        if footnote.id in self.caption.references:
                            # print('Footnote records: %s' % [c.to_primitive() for c in footnote.records])
                            for fn_compound in footnote.records:
                                row_compound.merge_contextual(fn_compound)

                    log.debug(row_compound.serialize())
                    if row_compound.serialize():
                        table_records.append(row_compound)

        # TODO: If no rows have name or label, see if one is in the caption

        # Include non-contextual caption records in the final output
        caption_records = [c for c in caption_records if not c.is_contextual]
        table_records += caption_records
        # print(table_records)
        return table_records

    # TODO: extend abbreviations property to include footnotes
    # TODO: Resolve footnote records into headers


class Cell(Sentence):
    word_tokenizer = FineWordTokenizer()
    # pos_tagger = NoneTagger()
    ner_tagger = NoneTagger()

    @memoized_property
    def abbreviation_definitions(self):
        """Empty list. Abbreviation detection is disabled within table cells."""
        return []

    @property
    def records(self):
        """Empty list. Individual cells don't provide records, this is handled by the parent Table."""
        return []
