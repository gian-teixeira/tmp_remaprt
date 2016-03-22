%=============================================================================
% JBCS.cls - estilo de artigo para o Journal of the Brazilian Computer Society
%
% v1.3 2010/12/15 Lisandro Zambenedetti Granville
% - Remoção de thankstitle %\ifx\@thankstitle\@empty \else \thanks{\@thankstitle}\fi
%
% v1.2 2006/10/10 Daniel Nehme Muller
% - LaTeX stile to JBCS
%
% Copyright (C) 2006 Daniel Nehme Müller
% Sociedade Brasileira de Computação (SBC)
% Porto Alegre, Brasil
%
% Baseado em / based on:
% RITA.cls - estilo de artigo para a Revista RITA
% v0.2 2002/07/30 avila
% - corrigida geração dos footnotes
% v0.1 2002/07/25 avila
% - versão inicial
% Copyright (C) 2002 Rafael Ávila
% Instituto de Informática - UFRGS
% Porto Alegre, Brasil
%
% This program is free software; you can redistribute it and/or modify
% it under the terms of the GNU General Public License as published by
% the Free Software Foundation; either version 2 of the License, or
% (at your option) any later version.
%
% This program is distributed in the hope that it will be useful,
% but WITHOUT ANY WARRANTY; without even the implied warranty of
% MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
% GNU General Public License for more details.
%
% You should have received a copy of the GNU General Public License
% along with this program; if not, write to the Free Software
% Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
%==========================================================================

%==========================================================================
% Identificação
%==========================================================================
\NeedsTeXFormat{LaTeX2e}
\ProvidesClass{JBCS}[2006/09/20 v1.1 Article to Journal of the Brazilian Computer Society]

%==========================================================================
% Declarações preliminares
%==========================================================================
\DeclareOption*{\PassOptionsToClass{\CurrentOption}{article}}
\ProcessOptions\relax
\LoadClass[twoside,twocolumn]{article}
\RequirePackage{times}

%==========================================================================
% Margens e tamanho da página
%==========================================================================
%largura e altura do papel
%\setlength{\paperwidth}{210mm}\setlength{\paperheight}{283mm}
%largura e altura do texto
%\setlength{\textwidth}{168mm}\setlength{\textheight}{237mm}  %{245mm} %{227mm}
%margem esquerda em páginas ímpares e pares
%\setlength{\oddsidemargin}{25mm}
%\setlength{\evensidemargin}{17mm}\addtolength{\evensidemargin}{-\oddsidemargin}
%\addtolength{\oddsidemargin}{-\oddsidemargin}
%altura do cabeçalho - variável
%\setlength{\headheight}{\baselineskip}
% topo da folha até cabeçalho
%\setlength{\topmargin}{-13.5mm}%\addtolength{\topmargin}{\headheight}
% distância do topo do cabeçalho ao texto (topmargin + 12mm)
%\setlength{\headsep}{20.5mm}%\addtolength{\headsep}{-\headheight}
%\setlength{\footskip}{8mm}\addtolength{\footskip}{.5\baselineskip}

%largura e altura do papel
\setlength{\paperwidth}{210mm}\setlength{\paperheight}{283mm}%{267mm}
%largura e altura do texto
\setlength{\textwidth}{168mm}\setlength{\textheight}{228mm}  %{227mm}
%margem esquerda em páginas ímpares e pares
\setlength{\oddsidemargin}{25mm}
\setlength{\evensidemargin}{17mm}\addtolength{\evensidemargin}{-\oddsidemargin}
\addtolength{\oddsidemargin}{-\oddsidemargin}
% topo da folha até cabeçalho
\setlength{\topmargin}{17.2mm}\addtolength{\topmargin}{-1in}
% distância do topo do cabeçalho ao texto
\setlength{\headsep}{\topskip}\addtolength{\headsep}{14mm}
% distância ao número da página (no rodapé)
\setlength{\footskip}{8mm}\addtolength{\footskip}{.3\baselineskip}


%==========================================================================
% Formatação do fonte
%==========================================================================
\def\normalsize{\fontsize{10}{12.00pt}\selectfont%
\abovedisplayskip 1.5ex plus4pt minus2pt%
\belowdisplayskip \abovedisplayskip%
\abovedisplayshortskip 0pt plus4pt%
\belowdisplayshortskip 1.5ex plus4pt minus2pt}
\def\subnormalsize{\fontsize{9.5}{11pt}\selectfont}
\def\small{\fontsize{9}{10pt}\selectfont}
\def\footnotesize{\fontsize{8}{9pt}\selectfont}
\def\scriptsize{\fontsize{7}{8pt}\selectfont}
\def\tiny{\fontsize{5}{6pt}\selectfont}
% sublargesize is a tad smaller than large - 11pt
\def\sublargesize{\fontsize{11}{13.4pt}\selectfont}
\def\large{\fontsize{12}{14pt}\selectfont}
\def\Large{\fontsize{14}{17pt}\selectfont}
\def\LARGE{\fontsize{17}{20pt}\selectfont}
\def\huge{\fontsize{20}{24pt}\selectfont}
\def\Huge{\fontsize{24}{28pt}\selectfont}
\def\HUGE{\fontsize{31}{33pt}\selectfont}

%==========================================================================
% Definições diversas
%==========================================================================
\setlength{\parindent}{5mm}
%\setlength{\parskip}{2mm \@plus \p@}
\linespread{1}
\twocolumn
\columnsep 7truemm

%==========================================================================
% Cabeçalho e rodapé
%==========================================================================
\def\ps@JBCS{
  % cabecalho página ímpar
    \def\@oddhead{%
     \underline{%
      \begin{tabular}[t]{p{.97\textwidth}}   % largura da linha na página
       \begin{tabular}[t]{p{.90\columnwidth}} % largura do texto lado esq - nomes
       {\bf\sffamily\itshape{\small\@cabnames}} \raggedright
     \end{tabular}
     \hspace*{\fill}
     \begin{tabular}[t]{p{.90\columnwidth}}  % largura do texto lado dir - título
       {\bf\sffamily\itshape{\small\@cabtit}}  \raggedleft
     \end{tabular}
    \end{tabular}
    }
  }
  % a mesma definição, mas para o lado par
    \def\@evenhead{%
     \underline{%
      \begin{tabular}[t]{p{.97\textwidth}}
       \begin{tabular}[t]{p{.90\columnwidth}}
        {\bf\sffamily\itshape{\small\@cabnames}} \raggedright
      \end{tabular}
      \hfill
      \begin{tabular}[t]{p{.90\columnwidth}}
        {\bf\sffamily\itshape{\small\@cabtit}} \raggedleft
      \end{tabular}
     \end{tabular}
      }
    }
    %numeracao das páginas - pé da página, no centro
    \def\@oddfoot{\hfil\bf\normalsize\thepage\hfil}
    \def\@evenfoot{\hfil\bf\normalsize\thepage\hfil}
}
\def\ps@JBCSfirstpage{\ps@JBCS\let\@oddhead\@empty\let\@evenhead\@empty}
\pagestyle{JBCS}

%==========================================================================
% Título
%==========================================================================
\def\maketitle{\par
\renewcommand\thefootnote{\@fnsymbol\c@footnote}%
%    \def\@makefnmark{\rlap{\@textsuperscript{\normalfont\@thefnmark}}}%
%    \long\def\@makefntext##1{\parindent 1em\noindent
%            \hb@xt@1.8em{%
%                \hss\@textsuperscript{\normalfont\@thefnmark}}##1}%

 \twocolumn[\@maketitle]
 \@thanks


\renewcommand\thefootnote{\arabic{footnote}}%
\setcounter{footnote}{0}
}

\def\@maketitle{%
  \newpage\null
  \vskip 2em
 % \let \footnote \thanks
 %  \global\let\thanks\relax
   \global\let\@thanks\@empty
  \thispagestyle{empty}%
    \begin{center}
     \noindent{\HUGE\textbf{\@title}%
%      \ifx\@thankstitle\@empty \else \thanks{\@thankstitle}\fi
      \par}
     \vskip 1.5em
       {\lineskip .5em
       % quadros com os autores
      \begin{tabular}[t]{c}
       \begin{tabular}[t]{c}%{@{}c@{}}
        {\sublargesize\bf \@namea}
        \ifx\@thanksnamea\@empty \else \thanks{\@thanksnamea} \fi \\
        \normalsize \@addressa \relax
       \end{tabular}
      % caso tenha dois autores
       \ifx\@nameb\@empty  \gdef\@names{\@namea}%
        \else
        % \hskip 7truemm   % caso precise deixar mais espaco
         \begin{tabular}[t]{c}%{@{}c@{}}
           {\sublargesize\bf \@nameb}
           \ifx\@thanksnameb\@empty \else \thanks{\@thanksnameb} \fi \\
           \normalsize \@addressb \relax
         \end{tabular}
         \gdef\@names{\@namea, \@nameb}
       \fi
       % caso tenha tres autores
       \ifx\@named\@empty%
         \ifx\@namec\@empty\else%
          % \hskip 7truemm   % caso precise deixar mais espaco
             \begin{tabular}[t]{c}%{@{}c@{}}
               {\sublargesize\bf \@namec}
               \ifx\@thanksnamec\@empty \else \thanks{\@thanksnamec} \fi \\
               \normalsize \@addressc \relax
             \end{tabular}
             \gdef\@names{\@namea, \@nameb, \@namec}
           \fi
        \fi
      \end{tabular}
      % tabelas para o caso de quatro autores
      \ifx\@named\@empty\else%
       \begin{tabular}[t]{c}
         \begin{tabular}[t]{c}%{@{}c@{}}
          {\sublargesize\bf \@namec}
          \ifx\@thanksnamec\@empty \else \thanks{\@thanksnamec} \fi \\
          \normalsize \@addressc \relax
         \end{tabular}
        % \hskip 7truemm   % caso precise deixar mais espaco
         \begin{tabular}[t]{c}%{@{}c@{}}
           {\sublargesize\bf \@named}
           \ifx\@thanksnamec\@empty \else \thanks{\@thanksnamed} \fi \\
           \normalsize \@addressd \relax
         \end{tabular}
       \end{tabular}
       \gdef\@names{\@namea, \@nameb, \@namec, \@named}
      \fi
      \par}
    \end{center}
    \par
 \vskip 1.5em
 }

%==========================================================================
% Autor
%==========================================================================
% criação dos nomes em separado - até 4 (para formar o quadro de nomes)
\def\title#1{\gdef\@title{{#1}}}
\def\thankstitle#1{\gdef\@thankstitle{{#1}}}
\def\namea#1{\gdef\@namea{#1}}
\def\addressa#1{\gdef\@addressa{#1}}
\def\thanksnamea#1{\gdef\@thanksnamea{#1}}
\def\nameb#1{\gdef\@nameb{#1}}
\def\addressb#1{\gdef\@addressb{#1}}
\def\thanksnameb#1{\gdef\@thanksnameb{#1}}
\def\namec#1{\gdef\@namec{#1}}
\def\addressc#1{\gdef\@addressc{#1}}
\def\thanksnamec#1{\gdef\@thanksnamec{#1}}
\def\named#1{\gdef\@named{#1}}
\def\addressd#1{\gdef\@addressd{#1}}
\def\thanksnamed#1{\gdef\@thanksnamed{#1}}
\def\cabnames#1{\gdef\@cabnames{{#1}}}
\def\cabtit#1{\gdef\@cabtit{{#1}}}

\gdef\@title{{Title of Paper}}
\gdef\@namea{{Name of author}\\}
\gdef\@addressa{Address - Line 1 \\
               Address - Line 2 \\
               Address - Line 3}
\gdef\@cabnames{{Name of author}}
\gdef\@cabtit{{Title of Paper}}
\gdef\@thankstitle{}
\gdef\@thanksnamea{}
\gdef\@thanksnameb{}
\gdef\@thanksnamec{}
\gdef\@thanksnamed{}

%==========================================================================
% Resumo
%==========================================================================
\def\abstract{\begin{center}
{\large\bf Abstract\vspace{-.5em}\vspace{0pt}}
\end{center}  \par\it}
\def\endabstract{\par}

\def\resumo{\begin{center}
{\large\bf Resumo\vspace{-.5em}\vspace{0pt}}
\end{center}  \par\it}
\def\endresumo{\par}

%==========================================================================
% Palavras-chave
%==========================================================================
\def\keywords{\normalsize%
      {\bf\textit{Keywords: }}\,\relax%
      }
\def\endkeywords{\par}

\def\palavraschave{\normalsize%
      {\bf\textit{Palavras-chave: }}\,\relax%
      }
\def\endpalavraschave{\par}



%==========================================================================
% Seções
%==========================================================================

\def\@startsection#1#2#3#4#5#6#7{\if@noskipsec \leavevmode \fi
   \par \@tempskipa #4\relax
   \@afterindenttrue
   \ifdim \@tempskipa <\z@ \@tempskipa -\@tempskipa \@afterindentfalse\fi
   \addtolength{\@tempskipa}{-\parskip}
   \if@nobreak \everypar{}\else
     \addpenalty{\@secpenalty}\addvspace{\@tempskipa}  \fi
     \@ifstar
     {\@ssect{#1}{#2}{#3}{#4}{#5}{#6}{#7}}
     {\@dblarg{\@sect{#1}{#2}{#3}{#4}{#5}{#6}{#7}}}}

\def\@sect#1#2#3#4#5#6#7[#8]#9{
   \ifnum #2>\c@secnumdepth
      \def\@svsec{}
   \else
        \refstepcounter{#1}\edef\@svsec{{\csname the#1\endcsname.}\hskip 0.6em }
    \fi
   \@tempskipa #5\relax
   \ifdim \@tempskipa>\z@
      \begingroup #6\relax
      \ifnum #2 > 1  % if it is not a section ..
         %% header on the same line as section number
         \@hangfrom{\hskip #3\relax}{\sc\textbf{\@svsec\interlinepenalty \@M #8#7}\par}
      \else          % if it is a section ..
         \setbox1=\hbox{\sc\textbf{\@svsec #8#7}}
         \ifdim \wd1>\columnwidth
             \sc\textbf{\@svsec \noindent \interlinepenalty \@M #8#7}\par
         \else  % if it is section AND not wider then width of column
            \sc\textbf{\@svsec \noindent\interlinepenalty\@M #8#7} %\vskip\parskip\centerline\par
         \fi
      \fi
      \endgroup
      \csname #1mark\endcsname{#8}\addcontentsline
         {toc}{#1}{\ifnum #2>\c@secnumdepth \else
                      \protect\numberline{\csname the#1\endcsname}\fi
                    #8}
   \else
        \def\@svsechd{#6\hskip #3\@svsec #9#7\csname #1mark\endcsname
              {#8}\addcontentsline {toc}{#1}{\ifnum #2>\c@secnumdepth \else
               \protect\numberline{\csname the#1\endcsname}\fi
               #8}}
   \fi
   \@xsect{#5}}

\def\@ssect#1#2#3#4#5#6#7#8{\@tempskipa #5\relax
  \ifdim \@tempskipa>\z@
     \begingroup #6\relax
     \ifnum #2 > 1
         \@hangfrom{\hskip #3}{\interlinepenalty\@M #8#7\par}
     \else % if it is section AND not wider then width of column
         \setbox1=\hbox{#8#7}
         \ifdim \wd1>\columnwidth
             {#8#7\par}  %\centering
         \else
             %\vskip\parskip\centerline
             {#8#7}  %\par
         \fi
     \fi
     \endgroup
  \else
     \def\@svsechd{#6\hskip #3\relax #8#7}
  \fi
  \@xsect{#5}}

\def\@xsect#1{\@tempskipa #1\relax
      \ifdim \@tempskipa>\z@
       \par \nobreak
       \addtolength{\@tempskipa}{-\parskip}
       \vskip \@tempskipa
       \@afterheading
    \else \global\@nobreakfalse \global\@noskipsectrue
       \everypar{\if@noskipsec \global\@noskipsecfalse
                   \clubpenalty\@M \hskip -\parindent
                   \begingroup \@svsechd \endgroup \unskip
                   \hskip -#1
                  \else \clubpenalty \@clubpenalty
                    \everypar{}
                 \fi}
        \fi\ignorespaces}

\def\section{\@startsection{section}{1}{\z@}
 {6.5ex plus 0.5ex minus 0.5ex}{1pt plus 0.3ex}{\sc\bf\large}{}}
\def\subsection{\@startsection{subsection}{2}{\z@}
 {3.0ex plus 0.3ex minus .1ex}{0.01ex plus .0ex}{\sc\bf}{}}
\def\subsubsection{\@startsection{subsubsection}{3}{2ex}
 {3.0ex plus 0.3ex minus .1ex}{-1ex}{\sc\bf}{:}}


    % coloca referências no mesmo estilo de título de seção
\renewcommand\refname{\sc\textbf{References}}

%==========================================================================
% Formatação das legendas de figuras e tabelas
%==========================================================================
\long\def\@makecaption#1#2{
 \vskip 10pt
 \setbox\@tempboxa\hbox{\centering\footnotesize #1. #2}
 \ifdim \wd\@tempboxa >\hsize \centering\footnotesize #1. #2\par \else \hbox
to\hsize{\hfil\box\@tempboxa\hfil}
 \fi}

%==========================================================================
% Formatação das notas de rodapé
%==========================================================================
% redefinição da linha do rodapé
\renewcommand\footnoterule{%
  %\kern-3\p@
  \hrule\columnwidth %\@width.4
  %\kern2.6\p@
  }

% rodapé tem largura da coluna
\renewcommand\@makefntext[1]{%
  \parbox[t]{\columnwidth}{\mbox{\@makefnmark}#1}
  }

%%%% EOF
