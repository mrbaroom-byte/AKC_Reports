# Reorder children of OOXML property elements into schema order and drop duplicates (last one wins).
from lxml import etree
W = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
ORDER = {
 'pPr': 'pStyle keepNext keepLines pageBreakBefore framePr widowControl numPr suppressLineNumbers pBdr shd tabs suppressAutoHyphens kinsoku wordWrap overflowPunct topLinePunct autoSpaceDE autoSpaceDN bidi adjustRightInd snapToGrid spacing ind contextualSpacing mirrorIndents suppressOverlap jc textDirection textAlignment textboxTightWrap outlineLvl divId cnfStyle rPr sectPr pPrChange',
 'rPr': 'rStyle rFonts b bCs i iCs caps smallCaps strike dstrike outline shadow emboss imprint noProof snapToGrid vanish webHidden color spacing w kern position sz szCs highlight u effect bdr shd fitText vertAlign rtl cs em lang eastAsianLayout specVanish oMath',
 'tblPr': 'tblStyle tblpPr tblOverlap bidiVisual tblStyleRowBandSize tblStyleColBandSize tblW jc tblCellSpacing tblInd tblBorders shd tblLayout tblCellMar tblLook tblCaption tblDescription',
 'tcPr': 'cnfStyle tcW gridSpan hMerge vMerge tcBorders shd noWrap tcMar textDirection tcFitText vAlign hideMark',
 'sectPr': 'headerReference footerReference footnotePr endnotePr type pgSz pgMar paperSrc pgBorders lnNumType pgNumType cols formProt vAlign noEndnote titlePg textDirection bidi rtlGutter docGrid printerSettings sectPrChange',
 'tblBorders': 'top left start bottom right end insideH insideV',
 'tblCellMar': 'top left start bottom right end',
 'pBdr': 'top left bottom right between bar',
}
MULTI = {'headerReference', 'footerReference'}
RANK = {k: {n: i for i, n in enumerate(v.split())} for k, v in ORDER.items()}

def fix_tree(root):
    for tag, rank in RANK.items():
        for e in root.iter(W + tag):
            kids = list(e)
            seen = {}
            keep = []
            for k in kids:
                if not isinstance(k.tag, str): keep.append(k); continue
                ln = etree.QName(k).localname
                if ln in MULTI or ln not in rank: keep.append(k); continue
                if ln in seen: keep.remove(seen[ln])
                seen[ln] = k; keep.append(k)
            for k in kids: e.remove(k)
            keep.sort(key=lambda k: rank.get(etree.QName(k).localname, 999) if isinstance(k.tag, str) else 999)
            for k in keep: e.append(k)
    return root

def fix_bytes(b):
    root = etree.fromstring(b)
    fix_tree(root)
    return etree.tostring(root, xml_declaration=True, encoding='UTF-8', standalone=True)
