# -*- coding: utf-8 -*-
"""
chemdataextractor.reader.markup
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

XML and HTML readers based on lxml.

"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals
import logging
from abc import abstractmethod, ABCMeta
from collections import defaultdict

from lxml import etree
from lxml.etree import XMLParser
from lxml.html import HTMLParser
import six

from ..errors import ReaderError
from ..doc.document import Document
from ..doc.text import Title, Heading, Paragraph, Caption, Citation, Footnote, Text, Sentence
from ..doc.table import Table, Cell
from ..doc.figure import Figure
from ..scrape import INLINE_ELEMENTS
from ..scrape.clean import clean
from ..scrape.csstranslator import CssHTMLTranslator
from ..text import get_encoding
from .base import BaseReader


log = logging.getLogger(__name__)


class LxmlReader(six.with_metaclass(ABCMeta, BaseReader)):
    """Abstract base class for lxml-based readers."""

    #: A ``Cleaner`` instance to
    cleaners = [clean]

    root_css = 'html'
    title_css = 'h1'
    heading_css = 'h2, h3, h4, h5, h6'
    table_css = 'table'
    table_caption_css = 'caption'
    table_head_row_css = 'thead tr'
    table_body_row_css = 'tbody tr'
    table_cell_css = 'th, td'
    table_footnote_css = 'tfoot tr th'
    reference_css = 'a.ref'
    figure_css = 'figure'
    figure_caption_css = 'figcaption'
    citation_css = 'cite'
    ignore_css = 'a.ref sup'

    #: Inline elements
    inline_elements = INLINE_ELEMENTS

    def _parse_element_r(self, el, specials, refs, id=None, element_cls=Paragraph):
        """Recursively parse HTML/XML element and its children into a list of Document elements."""
        # print(self)
        elements = []
        if el.tag in {etree.Comment, etree.ProcessingInstruction}:
            return []
        # if el in refs:
        #     return [element_cls('', references=refs[el])]
        if el in specials:
            return specials[el]
        id = el.get('id', id)
        # print(id)
        references = refs.get(el, [])
        # print(references)
        # print(el.text)
        # print(element_cls)
        if el.text is not None:
            elements.append(element_cls(six.text_type(el.text), id=id, references=references))
        elif references:
            elements.append(element_cls('', id=id, references=references))

        for child in el:
            # br is a special case - technically inline, but we want to split
            # print(child.tag)

            if child.tag not in {etree.Comment, etree.ProcessingInstruction} and child.tag.lower() == 'br':
                elements.append(element_cls(''))

            child_elements = self._parse_element_r(child, specials=specials, refs=refs, id=id, element_cls=element_cls)
            if (self._is_inline(child) and len(elements) > 0 and len(child_elements) > 0 and
                    isinstance(elements[-1], (Text, Sentence)) and isinstance(child_elements[0], (Text, Sentence)) and
                    type(elements[-1]) == type(child_elements[0])):
                elements[-1] += child_elements.pop(0)
            elements.extend(child_elements)
            if child.tail is not None:
                if self._is_inline(child) and len(elements) > 0 and isinstance(elements[-1], element_cls):
                    elements[-1] += element_cls(six.text_type(child.tail), id=id)
                else:
                    elements.append(element_cls(six.text_type(child.tail), id=id))
        # print(elements)
        return elements

    def _parse_element(self, el, specials=None, refs=None, element_cls=Paragraph):
        """"""
        if specials is None:
            specials = {}
        if refs is None:
            refs = {}
        elements = self._parse_element_r(el, specials=specials, refs=refs, element_cls=element_cls)
        final_elements = []
        for element in elements:
            # Filter empty text elements
            if isinstance(element, Text):
                if element.text.strip():
                    final_elements.append(element)
            else:
                final_elements.append(element)
        # print(final_elements)
        return final_elements

    def _parse_text(self, el, refs=None, specials=None,  element_cls=Paragraph):
        """Like _parse_element but ensure a single element."""
        # print(self)
        if specials is None:
            specials = {}
        if refs is None:
            refs = {}
        elements = self._parse_element_r(el, specials=specials, refs=refs, element_cls=element_cls)
        # This occurs if the input element is self-closing... (some table td in NLM XML)
        if not elements:
            return [element_cls('')]
        element = elements[0]
        for next_element in elements[1:]:
            element += element_cls(' ') + next_element
        return [element]

    def _parse_figure(self, el, refs, specials):
        caps = self._css(self.figure_caption_css, el)
        caption = self._parse_text(caps[0], refs=refs, specials=specials, element_cls=Caption)[0] if caps else Caption('')
        fig = Figure(caption, id=el.get('id', None))
        return [fig]

    def _parse_table_rows(self, els, refs, specials):
        hdict = {}
        data = []
        for row, tr in enumerate(els):
            colnum = 0
            # if tr.get('rowsep') is not None:
            #     rows = tr.get('rowsep')
            # print(rows)
            # print(tr.find_all('rowsep')
            for td in self._css(self.table_cell_css, tr):
                cell = self._parse_text(td, refs=refs, specials=specials, element_cls=Cell)
                # print(cell)

                colspan = int(td.get('colspan', '1'))
                rowspan = int(td.get('rowspan', '1'))

                # 解决表格内容跨行问题
                if td.get('morerows') is not None:
                    more_row = int(td.get('morerows'))
                    rowspan = more_row + 1

                # 解决表格内容跨列问题
                # print(td.get('namest'))
                if td.get('namest') is not None and td.get('nameend') is not None:
                    beg = 0
                    curr = list(td.get('namest'))
                    # print(curr)
                    beg1 = []
                    for c in curr:
                        try:
                            beg1.append(int(c))
                        except:
                            continue
                    # print(len(beg1))
                    if len(beg1) == 1:
                        beg = beg1[0]
                    elif len(beg1) == 2:
                        beg = beg1[0]*10 + beg1[1]
                    elif len(beg1) == 3:
                        beg = beg1[0]*100 + beg[1]*10 + beg[2]
                    curr1 = list(td.get('nameend'))
                    temp_end = []
                    for c in curr1:
                        try:
                            en = int(c)
                            temp_end.append(en)
                        except:
                            continue
                    end = 0
                    # print(temp_end)
                    if len(temp_end) == 1:
                        end = temp_end[0]
                    elif len(temp_end) == 2:
                        end = temp_end[0]*10 + temp_end[1]
                    elif len(temp_end) == 3:
                        end = temp_end[0]*100 + temp_end[1]*10 + temp_end[2]
                    # print(end)
                    colspan = end - beg + 1
                # print(colspan)
                # print(rowspan, colspan)
                # 如何解决表格填充问题
                for i in range(colspan):
                    for j in range(rowspan):
                        rownum = row + j
                        if not rownum in hdict:
                            hdict[rownum] = {}
                        while colnum in hdict[rownum]:
                            colnum += 1
                        hdict[rownum][colnum] = cell[0] if len(cell) > 0 else Cell('')
                    colnum += 1

        rows = []
        for row in sorted(hdict):
            rows.append([])
            for col in sorted(hdict[row]):
                rows[-1].append(hdict[row][col])

        # for r in rows:
        #     for i in range(len(max(rows, key=len)) - len(r)):
        #         r.extend([Cell('')] * (len(max(rows, key=len)) - len(r)))
        # print(rows)

        rows = [r for r in rows if any(r)]
        # print(rows)
        return rows

    def _parse_table_footnotes(self, fns, refs, specials):
        # print(self._parse_text)
        # print(fns)
        return [self._parse_text(fn, refs=refs, specials=specials, element_cls=Footnote)[0] for fn in fns]

    def _parse_reference(self, el):
        """Return reference ID from href or text content."""
        if '#' in el.get('href', ''):
            return [el.get('href').split('#', 1)[1]]
        elif 'rid' in el.attrib:
            return [el.attrib['rid']]
        elif 'idref' in el.attrib:
            return [el.attrib['idref']]
        else:
            return [''.join(el.itertext()).strip()]

    def _parse_table(self, el, refs, specials):
        caps = self._css(self.table_caption_css, el)
        caption = self._parse_text(caps[0], refs=refs, specials=specials, element_cls=Caption)[0] if caps else Caption('')
        hrows = self._parse_table_rows(self._css(self.table_head_row_css, el), refs=refs, specials=specials)
        rows = self._parse_table_rows(self._css(self.table_body_row_css, el), refs=refs, specials=specials)
        footnotes = self._parse_table_footnotes(self._css(self.table_footnote_css, el), refs=refs, specials=specials)
        tab = Table(caption, headings=hrows, rows=rows, footnotes=footnotes, id=el.get('id', None))
        # print(specials)
        return [tab]

    def _xpath(self, query, root):
        result = root.xpath(query, smart_strings=False)
        if type(result) is not list:
            result = [result]
        log.debug('Selecting XPath: {}: {}'.format(query, result))
        return result

    def _css(self, query, root):
        return self._xpath(CssHTMLTranslator().css_to_xpath(query), root)

    def _is_inline(self, element):
        """Return True if an element is inline."""
        if element.tag not in {etree.Comment, etree.ProcessingInstruction} and element.tag.lower() in self.inline_elements:
            return True
        return False

    @abstractmethod
    def _make_tree(self, fstring):
        """Read a string into an lxml elementtree."""
        pass

    def parse(self, fstring):
        root = self._make_tree(fstring)
        if root is None:
            raise ReaderError
        root = self._css(self.root_css, root)[0]
        for cleaner in self.cleaners:
            cleaner(root)
        specials = {}
        refs = defaultdict(list)
        titles = self._css(self.title_css, root)
        headings = self._css(self.heading_css, root)
        figures = self._css(self.figure_css, root)
        tables = self._css(self.table_css, root)
        citations = self._css(self.citation_css, root)
        references = self._css(self.reference_css, root)
        ignores = self._css(self.ignore_css, root)
        for reference in references:
            refs[reference.getparent()].extend(self._parse_reference(reference))
        for ignore in ignores:
            specials[ignore] = []
        for title in titles:
            specials[title] = self._parse_text(title, element_cls=Title, refs=refs, specials=specials)
        for heading in headings:
            specials[heading] = self._parse_text(heading, element_cls=Heading, refs=refs, specials=specials)
        for figure in figures:
            specials[figure] = self._parse_figure(figure, refs=refs, specials=specials)
        for table in tables:
            specials[table] = self._parse_table(table, refs=refs, specials=specials)
        for citation in citations:
            specials[citation] = self._parse_text(citation, element_cls=Citation, refs=refs, specials=specials)
        elements = self._parse_element(root, specials=specials, refs=refs)
        return Document(*elements)


class XmlReader(LxmlReader):
    """Reader for generic XML documents."""

    def detect(self, fstring, fname=None):
        """"""
        if fname and not fname.endswith('.xml'):
            return False
        return True

    def _make_tree(self, fstring):
        root = etree.fromstring(fstring, parser=XMLParser(recover=True, encoding=get_encoding(fstring)))
        # print(root)
        return root


class HtmlReader(LxmlReader):
    """Reader for generic HTML documents."""

    def detect(self, fstring, fname=None):
        """"""
        if fname and not (fname.endswith('.html') or fname.endswith('.htm')):
            return False
        return True

    def _make_tree(self, fstring):
        root = etree.fromstring(fstring, parser=HTMLParser(encoding=get_encoding(fstring)))
        return root
