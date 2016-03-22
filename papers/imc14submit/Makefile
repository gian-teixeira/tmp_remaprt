LATEX=latex
BIBTEX=bibtex
DVIPDFM=dvipdfm
DVIPS=dvips

EXTRAFILES=$(wildcard *.tex)

BASENAME=paper
BIBNAME=references.bib

all:
	pdflatex $(BASENAME)
	bibtex $(BASENAME)
	pdflatex $(BASENAME)
	pdflatex $(BASENAME)

open:
	xpdf -rv $(BASENAME).pdf &

clean:
	\rm -rf $(BASENAME).aux $(BASENAME).dvi $(BASENAME).log $(BASENAME).bbl $(BASENAME).out $(BASENAME).blg $(BASENAME).ps $(BASENAME).pdf *~


#	bibtex $(BASENAME)
