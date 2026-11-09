"""
report_md.py  —  Genera l'informe d'anonimització en Markdown (ca/es/en)

Tot valor que prové del CSV o de l'usuari (noms d'ítem, valors, etiquetes,
noms de fitxer) passa per `_code` o `_txt`: `markdown` deixa passar HTML cru,
i l'informe HTML s'obre al navegador del DPO.
"""
import datetime
import html
import re


def _txt(value) -> str:
    """Text pla segur dins de Markdown/HTML (també dins de cel·les de taula)."""
    s = html.escape(str(value).replace("\n", " "), quote=False)
    return re.sub(r"([\\`*_\[\]|])", r"\\\1", s)


def _code(value) -> str:
    """Code span segur: el delimitador és més llarg que qualsevol tira de
    backticks del valor, perquè el valor no pugui tancar-lo i escapar-se'n.
    Markdown ja escapa `<`, `>` i `&` dins dels code spans."""
    s = str(value).replace("\n", " ")
    if not s.strip():
        return '`""`'
    longest = max((len(m) for m in re.findall(r"`+", s)), default=0)
    fence   = "`" * (longest + 1)
    pad     = " " if longest else ""
    return f"{fence}{pad}{s}{pad}{fence}"

T = {
"ca": {
"title":"Informe d'Anonimització de Dades Clíniques",
"subtitle":"Document tècnic per al Delegat/ada de Protecció de Dades",
"generated":"Generat el","tool":"Eina","version":"Versió",
"filename":"Fitxer processat","lang":"Idioma de l'informe","lang_val":"Català","project":"Projecte","project_val":"Fase post-Datathon InCa i pilots del projecte TSI «EU Health Hub – Investing in Resilient Health Systems»",
"s_summary":"1. Resum executiu",
"s_dataset":"2. Descripció del dataset original",
"s_methodology":"3. Metodologia d'anonimització",
"s_classification":"4. Classificació dels ítems",
"s_generalizations":"5. Generalitzacions aplicades als quasi-identificadors",
"s_imputation":"6. Tractament dels valors absents (NaN)",
"s_kanon":"7. Aplicació de la k-anonimitat",
"s_results":"8. Resultats i mètriques comparatives",
"s_eq_classes":"9. Anàlisi de les classes d'equivalència",
"s_guarantees":"10. Garanties de seguretat del dataset",
"s_conclusions":"11. Conclusió i certificació",
"summary_intro":("Aquest informe documenta el procés d'anonimització aplicat al dataset indicat, "
"seguint els principis de minimització de dades i protecció de la privacitat "
"establerts pel Reglament General de Protecció de Dades (RGPD, Reglament UE 2016/679) "
"i la Llei Orgànica 3/2018 de Protecció de Dades Personals i garantia dels drets digitals (LOPDGDD). "
"El procés ha estat realitzat mitjançant l'eina **Local Anonymizer**, "
"que opera íntegrament en local sense transmetre cap dada a serveis externs."),
"summary_method":("La tècnica principal aplicada és la **k-anonimitat**, que garanteix que cada "
"combinació de quasi-identificadors aparegui en almenys **k** pacients, "
"de manera que cap pacient es pugui singularitzar per aquests atributs. "
"Complementàriament, s'han pseudonimitzat els identificadors directes amb un hash amb clau secreta "
"i s'han convertit les dates a delta temporal."),
"summary_result":"El resultat del procés ha estat:",
"kanon_label":"K-anonimitat","none":"_(cap)_","and_more":"i {n} més",
"ds_patients":"Pacients únics","ds_records":"Registres totals","ds_items":"Variables (ítems)",
"ds_date_range":"Rang de dates","ds_col_mapping":"Correspondència de columnes (columna original al CSV → columna canònica interna)",
"ds_file":"Fitxer",
"ds_dropped":"Files descartades (sense pacient o sense variable)",
"ds_duplicates":"Files idèntiques repetides (conservades)","ds_ignored":"Columnes ignorades (no arriben a la sortida)",
"meth_intro":("El procés d'anonimització s'ha estructurat en les fases següents, "
"aplicades de forma seqüencial sobre el dataset:"),
"meth_step1_title":"Fase 1 — Normalització i coherència del dataset",
"meth_step1_body":("Abans de cap transformació s'ha assegurat la coherència del dataset:\n\n"
"- Les columnes de cada fitxer s'han mapejat als noms canònics interns (`pacient`, `data`, `item`, `valor`), "
"per àlies habituals (`patient_id`, `variable`, `value`…) o amb confirmació explícita de l'usuari. Qualsevol altra columna es descarta i no arriba a la sortida.\n"
"- Tots els valors s'han llegit com a text, sense inferència de tipus: els identificadors es conserven "
"exactament (p. ex. `0012` no passa a `12` ni a `12.0`) i són comparables entre fitxers.\n"
"- S'han eliminat els espais als extrems dels identificadors i descartat les files sense pacient o sense variable.\n"
"- Quan hi ha més d'un fitxer, s'han combinat en un sol dataset abans de transformar res, de manera que "
"les dates, la imputació i la k-anonimitat es calculen sobre tota la informació de cada pacient."),
"meth_step2_title":"Fase 2 — Transformació de dates",
"meth_step2_body":("Totes les dates absolutes han estat substituïdes per un **delta enter de minuts** "
"calculat com la diferència respecte a la primera visita de cada pacient. "
"Això preserva els intervals temporals clínicament rellevants — incloent diferències intra-dia "
"de minuts entre observacions — sense revelar dates absolutes.\n\n"
"- Primera visita de cada pacient → valor `0`\n"
"- Visites posteriors → nombre de minuts transcorreguts des de la primera\n"
"- Si el timestamp original només contenia data (sense hora), el delta serà múltiple de 1440\n"
"- Les dates originals no es conserven en cap forma al dataset de sortida"),
"meth_step3_title":"Fase 6 — Pseudonimització de l'identificador de pacient",
"meth_step3_body":("L'identificador de pacient ha estat substituït per un **HMAC-SHA256** "
"truncat als primers 12 caràcters hexadecimals, amb el prefix `H-`. "
"La clau de l'HMAC és **aleatòria, secreta i exclusiva d'aquesta sessió**: només ha existit "
"a la memòria de l'eina durant el procés i no es conserva enlloc. Sense la clau no és possible "
"recalcular els hashos a partir d'una llista d'identificadors candidats (atac de diccionari), "
"i un cop tancada la sessió la correspondència pacient → hash és **irrecuperable**. "
"El mateix pacient rep el mateix hash a tots els fitxers d'aquesta sessió.\n\n"
"La pseudonimització s'aplica **al final del procés**, un cop el dataset és coherent, agrupat i k-anònim, "
"i només sobre els registres que es publiquen."),
"meth_step4_title":"Fase 3 — Imputació de valors absents",
"meth_step4_body":("Els valors absents (NaN) dels quasi-identificadors han estat imputats sobre els "
"valors originals, abans de generalitzar, per evitar la formació de grups d'equivalència unitaris:\n\n"
"- **Variables categòriques**: substituïts per `Desconocido`\n"
"- **Variables numèriques**: substituïts per la mediana de l'ítem al dataset"),
"meth_step5_title":"Fase 4 — Generalització de quasi-identificadors",
"meth_step5_body":("Els ítems classificats com a **quasi-identificadors** han estat generalitzats "
"per reduir la seva granularitat i limitar el risc de reidentificació per creuament. "
"Per a variables numèriques s'han definit intervals (binning); "
"per a variables categòriques s'han agrupat valors en categories de major amplitud. "
"Els valors numèrics fora dels intervals definits s'etiqueten `Fuera de rango` i els no "
"interpretables com a número, `Desconocido`; el recompte de cada cas consta a la secció 5."),
"meth_step6_title":"Fase 5 — K-anonimitat per supressió",
"meth_step6_body":("S'ha aplicat el model de **k-anonimitat** (Sweeney, 2002) sobre les combinacions "
"de quasi-identificadors generalitzats.\n\n"
"1. Construeix la signatura de cada pacient: per a cada quasi-identificador, el conjunt de "
"valors distints que pren al llarg de **totes** les seves visites (p. ex. `60-64 | 65+`)\n"
"2. Agrupa els pacients per signatura i identifica els grups (classes d'equivalència) amb menys de **k** pacients\n"
"3. Elimina tots els registres dels pacients en grups no conformes\n\n"
"La supressió s'aplica a nivell de **pacient complet** per preservar la coherència del dataset. "
"Com que la signatura inclou tots els valors publicats, la garantia de k es compleix també "
"quan un quasi-identificador canvia entre visites."),
"cls_intro":"L'usuari ha classificat cada ítem del dataset en una de les categories següents:",
"cls_quasi":"Quasi-identificadors","cls_nonid":"No identificatius (sense canvis)",
"cls_quasi_desc":("Atributs que, tot sols o combinats amb d'altres, podrien permetre la "
"reidentificació d'un individu per creuament amb fonts externes. "
"Han estat generalitzats i inclosos en el model de k-anonimitat."),
"cls_nonid_desc":("Atributs amb nul·la o molt baixa capacitat de reidentificació. "
"Es mantenen sense modificació al dataset de sortida."),
"gen_intro":"Per a cada quasi-identificador s'ha aplicat la transformació següent:",
"gen_type_bins":"Binning numèric (intervals)","gen_type_mapping":"Mapeig de categories",
"gen_bins_label":"Punts de tall","gen_labels_label":"Etiquetes resultants",
"gen_mapping_label":"Mapeig de valors","gen_unmapped":"Valors no assignats",
"gen_none":"Sense transformació (valor original)",
"gen_log_non_numeric":"Registres no numèrics → `Desconocido`",
"gen_log_out_of_range":"Registres fora dels intervals → `Fuera de rango`",
"gen_log_unmapped":"Registres sense correspondència → etiqueta de no assignats",
"imp_intro":"S'han imputat els valors absents als quasi-identificadors següents:",
"imp_none":"No s'ha detectat cap valor absent als quasi-identificadors. No s'ha aplicat imputació.",
"imp_item":"Ítem","imp_n":"Registres imputats","imp_strat":"Estratègia",
"kan_k_used":"Valor de k utilitzat","kan_quasi_items":"Quasi-identificadors considerats",
"kan_note":("La k-anonimitat garanteix que cada individu al dataset sigui "
"indistingible d'almenys **k−1** altres individus. Un valor de k={k} implica que "
"cap individu pot ser singularitzat amb una probabilitat superior a 1/{k}."),
"res_before":"Abans de l'anonimització","res_after":"Després de l'anonimització",
"res_patients":"Pacients","res_records":"Registres",
"res_suppressed_p":"Pacients suprimits","res_suppressed_r":"Registres suprimits",
"res_pct":"Percentatge de pèrdua",
"res_visits_min":"Mínim de visites/pacient","res_visits_max":"Màxim de visites/pacient",
"res_visits_mean":"Mitjana de visites/pacient",
"eq_total":"Total de grups (classes d'equivalència)","eq_conforming":"Grups conformes (≥ k)",
"eq_suppressed":"Grups suprimits (< k)","eq_min":"Mida mínima de grup",
"eq_max":"Mida màxima de grup","eq_mean":"Mida mitjana de grup",
"eq_dist_title":"Distribució de mides de grup","eq_size":"Mida del grup","eq_ngroups":"Nombre de grups",
"eq_suppressed_detail":"Detall dels grups suprimits (fins a 20)",
"eq_none_suppressed":"Cap grup ha estat suprimit. Tots els pacients compleixen el criteri de k-anonimitat.",
# ── GARANTIES (substitueix limitacions) ──────────────────────────────────────
"guar_intro":("El dataset generat per aquest procés compta amb **tres capes de protecció complementàries** "
"per al seu ús a la fase post-Datathon InCa i als pilots del projecte TSI. "
"Cada capa actua de forma independent."),
"guar_layer1_title":"Capa 1 — Protecció tècnica (transformacions aplicades)",
"guar_layer1_body":("Les transformacions aplicades en aquest procés eliminen o ofusquen "
"tota la informació que permet la identificació directa o indirecta:\n\n"
"- **Identificador de pacient**: substituït per un HMAC-SHA256 amb clau secreta de sessió, "
"que no es conserva. Ni tan sols amb una llista d'identificadors candidats es pot reconstruir la correspondència.\n"
"- **Dates absolutes**: destruïdes i substituïdes per deltes relatius. "
"No és possible inferir quan va tenir lloc cap observació.\n"
"- **Quasi-identificadors**: generalitzats en categories o rangs. "
"La granularitat original (que podria permetre creuaments amb fonts externes) ha estat eliminada.\n"
"- **K-anonimitat**: garantia matemàtica que cap perfil de quasi-identificadors "
"és únic al dataset. Cada individu és indistingible d'almenys k−1 altres."),
"guar_layer2_title":"Capa 2 — Incertesa de presència (abast de l'extracció)",
"guar_layer2_body":("Cada dataset correspon a una extracció acotada: una línia assistencial i, a les noves "
"extraccions, l'any 2024. Quan l'extracció és una **mostra** de la població de referència, qui intenti "
"reidentificar una persona concreta **no pot saber a priori si aquella persona és al dataset**. Aquesta "
"incertesa, reconeguda per l'ENISA i el Grup de Treball de l'Article 29 com a factor mitigador del risc de "
"reidentificació, és independent de les transformacions tècniques.\n\n"
"Si l'extracció inclou tota la població de la línia i del període, aquesta incertesa no s'aplica i la protecció "
"descansa en les capes 1 i 3. El DPD ho ha de tenir en compte en valorar el risc residual."),
"guar_layer3_title":"Capa 3 — Controls organitzacionals i de l'entorn del projecte",
"guar_layer3_body":("L'accés a les dades es regeix per l'**Acord d'ús de dades i confidencialitat** de la fase "
"post-Datathon InCa i dels pilots del projecte TSI «EU Health Hub – Investing in Resilient Health Systems», "
"promogut pel Ministeri de Sanitat, l'OMS – Oficina Regional per a Europa i l'Instituto de Salud Carlos III (ISCIII):\n\n"
"- **Participants acreditats**: només hi accedeixen participants autoritzats que han signat l'acord, i com a màxim fins al 31 de maig de 2027.\n"
"- **Finalitat limitada**: revisió i harmonització de variables, ponderació i desenvolupament, avaluació i validació "
"de models, algorismes i anàlisis sobre complexitat i necessitats de cures.\n"
"- **Prohibició de reidentificació i de creuaments**: es prohibeix qualsevol intent de reidentificació i la combinació "
"amb fonts externes. Els creuaments entre conjunts del projecte requereixen autorització expressa dins de l'entorn segur de l'ISCIII.\n"
"- **Entorn segur**: es treballa als espais habilitats per l'ISCIII (SharePoint del projecte i aplicacions publicades a Red SARA). "
"La descàrrega només s'admet quan és imprescindible, en equips corporatius de la institució, mai en dispositius personals "
"ni en serveis al núvol o eines externes, incloses les d'intel·ligència artificial generativa, i les còpies locals s'eliminen en acabar cada tasca.\n"
"- **Incidències i responsabilitats**: qualsevol informació que permeti identificar una persona o accés no autoritzat es "
"comunica immediatament a la coordinació i a l'equip responsable de l'entorn de l'ISCIII. L'incompliment pot comportar la "
"retirada de l'accés i la comunicació a l'autoritat competent."),
"guar_summary_title":"Síntesi de les garanties",
"guar_summary_body":("Les tres capes es complementen:\n\n"
"| Capa | Tipus | Protecció aportada |\n"
"|------|-------|--------------------|\n"
"| Tècnica | K-anonimitat + HMAC amb clau de sessió + delta de minuts + generalització | Cap perfil dels quasi-identificadors seleccionats és compartit per menys de k pacients |\n"
"| Estadística | Extracció acotada i, si escau, mostreig | Incertesa sobre la presència de cada individu quan l'extracció és una mostra |\n"
"| Organitzacional | Acord d'ús de dades + SharePoint i Red SARA de l'ISCIII + participants acreditats | Control d'accés i responsabilitat legal |\n\n"
"**Un cop validat pel DPD, el dataset resultant es podrà incorporar a l'entorn autoritzat del projecte.**"),
# ── CONCLUSIONS ───────────────────────────────────────────────────────────────
"con_intro":("El dataset ha estat processat seguint les tècniques estàndard "
"d'anonimització estadística reconegudes per la normativa europea de protecció de dades "
"i les guies de l'ENISA. La combinació de la k-anonimitat amb els controls tècnics i "
"organitzacionals descrits redueix el risc de reidentificació en el context d'ús previst.\n\n"
"**La valoració final del risc residual correspon al DPD.**"),
"con_signed":"Certificació tècnica del procés:",
"con_items":[
"Les transformacions han estat aplicades de forma sistemàtica i documentada.",
"El valor de k garanteix la indistingibilitat dels individus del dataset final respecte dels quasi-identificadors seleccionats.",
"L'informe complet del procés queda disponible per a la seva revisió pel DPD/DPO.",
"L'identificador de pacient ha estat substituït, les dates d'observació convertides en deltes i només es conserven les 4 columnes del format.",
"Totes les decisions de classificació han estat preses per l'usuari responsable del centre.",
],
"con_closing":("Aquest informe ha estat generat automàticament per l'eina Local Anonymizer. "
"Les decisions de classificació i generalització de variables han estat preses per "
"l'usuari responsable del centre. L'eina no inspecciona el contingut de les variables no identificatives: "
"el responsable del centre ha d'assegurar que no inclouen text lliure, identificadors directes ni dates. "
"El DPD/DPO ha de revisar i validar aquest informe abans d'incorporar el dataset a l'entorn del projecte."),
},
}

T["es"] = {
"title":"Informe de Anonimización de Datos Clínicos",
"subtitle":"Documento técnico para el Delegado/a de Protección de Datos",
"generated":"Generado el","tool":"Herramienta","version":"Versión",
"filename":"Fichero procesado","lang":"Idioma del informe","lang_val":"Castellano","project":"Proyecto","project_val":"Fase post-Datathon InCa y pilotos del proyecto TSI «EU Health Hub – Investing in Resilient Health Systems»",
"s_summary":"1. Resumen ejecutivo","s_dataset":"2. Descripción del dataset original",
"s_methodology":"3. Metodología de anonimización","s_classification":"4. Clasificación de los ítems",
"s_generalizations":"5. Generalizaciones aplicadas a los cuasi-identificadores",
"s_imputation":"6. Tratamiento de los valores ausentes (NaN)",
"s_kanon":"7. Aplicación de la k-anonimidad","s_results":"8. Resultados y métricas comparativas",
"s_eq_classes":"9. Análisis de las clases de equivalencia",
"s_guarantees":"10. Garantías de seguridad del dataset",
"s_conclusions":"11. Conclusión y certificación",
"summary_intro":("Este informe documenta el proceso de anonimización aplicado al dataset indicado, "
"siguiendo los principios de minimización de datos y protección de la privacidad "
"establecidos por el Reglamento General de Protección de Datos (RGPD, Reglamento UE 2016/679) "
"y la Ley Orgánica 3/2018 de Protección de Datos Personales y garantía de los derechos digitales (LOPDGDD). "
"El proceso ha sido realizado mediante la herramienta **Local Anonymizer**, "
"que opera íntegramente en local sin transmitir ningún dato a servicios externos."),
"summary_method":("La técnica principal aplicada es la **k-anonimidad**, que garantiza que cada "
"combinación de cuasi-identificadores aparezca en al menos **k** pacientes, "
"de modo que ningún paciente pueda singularizarse por esos atributos. "
"Complementariamente, se han seudonimizado los identificadores directos con un hash con clave secreta "
"y se han convertido las fechas a delta temporal."),
"summary_result":"El resultado del proceso ha sido:",
"kanon_label":"K-anonimidad","none":"_(ninguno)_","and_more":"y {n} más",
"ds_patients":"Pacientes únicos","ds_records":"Registros totales","ds_items":"Variables (ítems)",
"ds_date_range":"Rango de fechas","ds_col_mapping":"Correspondencia de columnas (columna original en el CSV → columna canónica interna)",
"ds_file":"Fichero",
"ds_dropped":"Filas descartadas (sin paciente o sin variable)",
"ds_duplicates":"Filas idénticas repetidas (conservadas)","ds_ignored":"Columnas ignoradas (no llegan a la salida)",
"meth_intro":"El proceso de anonimización se ha estructurado en las siguientes fases secuenciales:",
"meth_step1_title":"Fase 1 — Normalización y coherencia del dataset",
"meth_step1_body":("Antes de cualquier transformación se ha asegurado la coherencia del dataset:\n\n"
"- Las columnas de cada fichero se han mapeado a los nombres canónicos internos (`pacient`, `data`, `item`, `valor`), "
"por alias habituales (`patient_id`, `variable`, `value`…) o con confirmación explícita del usuario. Cualquier otra columna se descarta y no llega a la salida.\n"
"- Todos los valores se han leído como texto, sin inferencia de tipos: los identificadores se conservan "
"exactamente (p. ej. `0012` no pasa a `12` ni a `12.0`) y son comparables entre ficheros.\n"
"- Se han eliminado los espacios en los extremos de los identificadores y descartado las filas sin paciente o sin variable.\n"
"- Cuando hay más de un fichero, se han combinado en un único dataset antes de transformar nada, de modo que "
"las fechas, la imputación y la k-anonimidad se calculan sobre toda la información de cada paciente."),
"meth_step2_title":"Fase 2 — Transformación de fechas",
"meth_step2_body":("Todas las fechas absolutas han sido sustituidas por un **delta entero de minutos** "
"calculado como la diferencia respecto a la primera visita de cada paciente. "
"Esto preserva los intervalos temporales clínicamente relevantes — incluyendo diferencias "
"intra-día de minutos entre observaciones — sin revelar fechas absolutas.\n\n"
"- Primera visita → valor `0`\n"
"- Visitas posteriores → minutos transcurridos desde la primera\n"
"- Si el timestamp original solo contenía fecha (sin hora), el delta será múltiplo de 1440\n"
"- Las fechas originales no se conservan en ninguna forma"),
"meth_step3_title":"Fase 6 — Seudonimización del identificador de paciente",
"meth_step3_body":("El identificador de paciente ha sido sustituido por un **HMAC-SHA256** truncado "
"(12 caracteres hex, prefijo `H-`). La clave del HMAC es **aleatoria, secreta y exclusiva de esta "
"sesión**: solo ha existido en la memoria de la herramienta durante el proceso y no se conserva. "
"Sin la clave no es posible recalcular los hashes a partir de una lista de identificadores "
"candidatos (ataque de diccionario), y una vez cerrada la sesión la correspondencia "
"paciente → hash es **irrecuperable**. El mismo paciente recibe el mismo hash en todos los ficheros de esta sesión.\n\n"
"La seudonimización se aplica **al final del proceso**, una vez el dataset es coherente, está agrupado y es k-anónimo, "
"y solo sobre los registros que se publican."),
"meth_step4_title":"Fase 3 — Imputación de valores ausentes",
"meth_step4_body":("Los valores ausentes de los cuasi-identificadores han sido imputados sobre los valores "
"originales, antes de generalizar:\n\n"
"- **Categóricas**: `Desconocido`\n- **Numéricas**: mediana del ítem"),
"meth_step5_title":"Fase 4 — Generalización de cuasi-identificadores",
"meth_step5_body":("Los ítems clasificados como cuasi-identificadores han sido generalizados mediante intervalos "
"numéricos o agrupación de categorías, eliminando la granularidad que podría facilitar el cruce con fuentes externas. "
"Los valores numéricos fuera de los intervalos definidos se etiquetan `Fuera de rango` y los no interpretables "
"como número, `Desconocido`; el recuento de cada caso consta en la sección 5."),
"meth_step6_title":"Fase 5 — K-anonimidad por supresión",
"meth_step6_body":("Se ha aplicado el modelo de **k-anonimidad** (Sweeney, 2002):\n\n"
"1. Construye la firma de cada paciente: para cada cuasi-identificador, el conjunto de valores distintos "
"que toma a lo largo de **todas** sus visitas (p. ej. `60-64 | 65+`)\n"
"2. Agrupa los pacientes por firma e identifica los grupos con menos de k pacientes\n"
"3. Elimina todos los registros de pacientes en grupos no conformes\n\n"
"La supresión se aplica a nivel de **paciente completo**. Como la firma incluye todos los valores "
"publicados, la garantía de k se cumple también cuando un cuasi-identificador cambia entre visitas."),
"cls_intro":"El usuario ha clasificado cada ítem en una de las categorías siguientes:",
"cls_quasi":"Cuasi-identificadores","cls_nonid":"No identificativos (sin cambios)",
"cls_quasi_desc":"Atributos que podrían permitir la reidentificación por cruce con fuentes externas. Han sido generalizados e incluidos en la k-anonimidad.",
"cls_nonid_desc":"Atributos con muy baja capacidad de reidentificación. Se mantienen sin modificación.",
"gen_intro":"Para cada cuasi-identificador se ha aplicado la transformación siguiente:",
"gen_type_bins":"Binning numérico (intervalos)","gen_type_mapping":"Mapeo de categorías",
"gen_bins_label":"Puntos de corte","gen_labels_label":"Etiquetas resultantes",
"gen_mapping_label":"Mapeo de valores","gen_unmapped":"Valores no asignados",
"gen_none":"Sin transformación (valor original)",
"gen_log_non_numeric":"Registros no numéricos → `Desconocido`",
"gen_log_out_of_range":"Registros fuera de los intervalos → `Fuera de rango`",
"gen_log_unmapped":"Registros sin correspondencia → etiqueta de no asignados",
"imp_intro":"Se han imputado los valores ausentes en los cuasi-identificadores siguientes:",
"imp_none":"No se detectaron valores ausentes en los cuasi-identificadores. No se aplicó imputación.",
"imp_item":"Ítem","imp_n":"Registros imputados","imp_strat":"Estrategia",
"kan_k_used":"Valor de k utilizado","kan_quasi_items":"Cuasi-identificadores considerados",
"kan_note":("La k-anonimidad garantiza que cada individuo sea indistinguible de al menos **k−1** otros. "
"Con k={k}, ningún individuo puede ser singularizado con probabilidad superior a 1/{k}."),
"res_before":"Antes de la anonimización","res_after":"Después de la anonimización",
"res_patients":"Pacientes","res_records":"Registros",
"res_suppressed_p":"Pacientes suprimidos","res_suppressed_r":"Registros suprimidos",
"res_pct":"Porcentaje de pérdida",
"res_visits_min":"Mín. visitas/paciente","res_visits_max":"Máx. visitas/paciente","res_visits_mean":"Media visitas/paciente",
"eq_total":"Total de grupos (clases de equivalencia)","eq_conforming":"Grupos conformes (≥ k)",
"eq_suppressed":"Grupos suprimidos (< k)","eq_min":"Tamaño mínimo de grupo",
"eq_max":"Tamaño máximo de grupo","eq_mean":"Tamaño medio de grupo",
"eq_dist_title":"Distribución de tamaños de grupo","eq_size":"Tamaño del grupo","eq_ngroups":"Nº de grupos",
"eq_suppressed_detail":"Detalle de grupos suprimidos (hasta 20)",
"eq_none_suppressed":"Ningún grupo suprimido. Todos los pacientes cumplen el criterio de k-anonimidad.",
"guar_intro":("El dataset generado por este proceso cuenta con **tres capas de protección complementarias** "
"para su uso en la fase post-Datathon InCa y en los pilotos del proyecto TSI. "
"Cada capa actúa de forma independiente."),
"guar_layer1_title":"Capa 1 — Protección técnica (transformaciones aplicadas)",
"guar_layer1_body":("Las transformaciones aplicadas eliminan u ofuscan toda la información "
"que permite la identificación directa o indirecta:\n\n"
"- **Identificador de paciente**: sustituido por un HMAC-SHA256 con clave secreta de sesión, "
"que no se conserva. Ni siquiera con una lista de identificadores candidatos se puede reconstruir la correspondencia.\n"
"- **Fechas absolutas**: destruidas y sustituidas por deltas relativos. "
"No es posible inferir cuándo tuvo lugar ninguna observación.\n"
"- **Cuasi-identificadores**: generalizados en categorías o rangos. "
"La granularidad original ha sido eliminada.\n"
"- **K-anonimidad**: garantía matemática de que ningún perfil de cuasi-identificadores "
"es único en el dataset. Cada individuo es indistinguible de al menos k−1 otros."),
"guar_layer2_title":"Capa 2 — Incertidumbre de presencia (alcance de la extracción)",
"guar_layer2_body":("Cada dataset corresponde a una extracción acotada: una línea asistencial y, en las nuevas "
"extracciones, el año 2024. Cuando la extracción es una **muestra** de la población de referencia, quien intente "
"reidentificar a una persona concreta **no puede saber a priori si esa persona está en el dataset**. Esta "
"incertidumbre, reconocida por la ENISA y el Grupo de Trabajo del Artículo 29 como factor mitigador del riesgo de "
"reidentificación, es independiente de las transformaciones técnicas.\n\n"
"Si la extracción incluye a toda la población de la línea y del período, esta incertidumbre no se aplica y la protección "
"descansa en las capas 1 y 3. El DPD debe tenerlo en cuenta al valorar el riesgo residual."),
"guar_layer3_title":"Capa 3 — Controles organizacionales y del entorno del proyecto",
"guar_layer3_body":("El acceso a los datos se rige por el **Acuerdo de uso de datos y confidencialidad** de la fase "
"post-Datathon InCa y de los pilotos del proyecto TSI «EU Health Hub – Investing in Resilient Health Systems», "
"promovido por el Ministerio de Sanidad, la OMS – Oficina Regional para Europa y el Instituto de Salud Carlos III (ISCIII):\n\n"
"- **Participantes acreditados**: solo acceden participantes autorizados que han firmado el acuerdo, y como máximo hasta el 31 de mayo de 2027.\n"
"- **Finalidad limitada**: revisión y armonización de variables, ponderación y desarrollo, evaluación y validación "
"de modelos, algoritmos y análisis sobre complejidad y necesidades de cuidados.\n"
"- **Prohibición de reidentificación y de cruces**: se prohíbe cualquier intento de reidentificación y la combinación "
"con fuentes externas. Los cruces entre conjuntos del proyecto requieren autorización expresa dentro del entorno seguro del ISCIII.\n"
"- **Entorno seguro**: se trabaja en los espacios habilitados por el ISCIII (SharePoint del proyecto y aplicaciones publicadas en Red SARA). "
"La descarga solo se admite cuando es imprescindible, en equipos corporativos de la institución, nunca en dispositivos personales "
"ni en servicios en la nube o herramientas externas, incluidas las de inteligencia artificial generativa, y las copias locales se eliminan al finalizar cada tarea.\n"
"- **Incidencias y responsabilidades**: cualquier información que permita identificar a una persona o acceso no autorizado se "
"comunica de inmediato a la coordinación y al equipo responsable del entorno del ISCIII. El incumplimiento puede conllevar la "
"retirada del acceso y la comunicación a la autoridad competente."),
"guar_summary_title":"Síntesis de las garantías",
"guar_summary_body":("Las tres capas se complementan:\n\n"
"| Capa | Tipo | Protección aportada |\n"
"|------|------|---------------------|\n"
"| Técnica | K-anonimidad + HMAC con clave de sesión + delta de minutos + generalización | Ningún perfil de los cuasi-identificadores seleccionados es compartido por menos de k pacientes |\n"
"| Estadística | Extracción acotada y, si procede, muestreo | Incertidumbre sobre la presencia de cada individuo cuando la extracción es una muestra |\n"
"| Organizacional | Acuerdo de uso de datos + SharePoint y Red SARA del ISCIII + participantes acreditados | Control de acceso y responsabilidad legal |\n\n"
"**Una vez validado por el DPD, el dataset resultante podrá incorporarse al entorno autorizado del proyecto.**"),
"con_intro":("El dataset ha sido procesado siguiendo las técnicas estándar de anonimización "
"estadística reconocidas por la normativa europea de protección de datos y las guías de la ENISA. "
"La combinación de la k-anonimidad con los controles técnicos y organizacionales descritos "
"reduce el riesgo de reidentificación en el contexto de uso previsto.\n\n"
"**La valoración final del riesgo residual corresponde al DPD.**"),
"con_signed":"Certificación técnica del proceso:",
"con_items":[
"Las transformaciones han sido aplicadas de forma sistemática y documentada.",
"El valor de k garantiza la indistinguibilidad de los individuos del dataset final respecto de los cuasi-identificadores seleccionados.",
"El informe completo del proceso queda disponible para su revisión por el DPD/DPO.",
"El identificador de paciente ha sido sustituido, las fechas de observación convertidas en deltas y solo se conservan las 4 columnas del formato.",
"Todas las decisiones de clasificación han sido tomadas por el usuario responsable del centro.",
],
"con_closing":("Informe generado automáticamente por Local Anonymizer. "
"Las decisiones de clasificación y generalización han sido tomadas por el usuario responsable. "
"La herramienta no inspecciona el contenido de las variables no identificativas: "
"el responsable del centro debe asegurar que no incluyen texto libre, identificadores directos ni fechas. "
"El DPD/DPO debe revisar y validar este informe antes de incorporar el dataset al entorno del proyecto."),
}

T["en"] = {
"title":"Clinical Data Anonymization Report",
"subtitle":"Technical document for the Data Protection Officer",
"generated":"Generated on","tool":"Tool","version":"Version",
"filename":"Processed file","lang":"Report language","lang_val":"English","project":"Project","project_val":"Post-Datathon InCa phase and pilots of the TSI project “EU Health Hub – Investing in Resilient Health Systems”",
"s_summary":"1. Executive Summary","s_dataset":"2. Original Dataset Description",
"s_methodology":"3. Anonymization Methodology","s_classification":"4. Item Classification",
"s_generalizations":"5. Generalizations Applied to Quasi-identifiers",
"s_imputation":"6. Missing Value Treatment","s_kanon":"7. Application of K-anonymity",
"s_results":"8. Results and Comparative Metrics","s_eq_classes":"9. Equivalence Class Analysis",
"s_guarantees":"10. Dataset Security Guarantees",
"s_conclusions":"11. Conclusion and Certification",
"summary_intro":("This report documents the anonymization process applied to the indicated dataset, "
"following the data minimization and privacy protection principles established by the "
"General Data Protection Regulation (GDPR, EU Regulation 2016/679). "
"The process was carried out using **Local Anonymizer**, which operates entirely "
"locally without transmitting any data to external services."),
"summary_method":("The main technique applied is **k-anonymity**, which guarantees "
"that each quasi-identifier combination appears in at least **k** patients, "
"so no patient can be singled out by those attributes. Complementary protections "
"include keyed-hash pseudonymization of direct identifiers and temporal delta conversion of dates."),
"summary_result":"The outcome of the process was:",
"kanon_label":"K-anonymity","none":"_(none)_","and_more":"and {n} more",
"ds_patients":"Unique patients","ds_records":"Total records","ds_items":"Variables (items)",
"ds_date_range":"Date range","ds_col_mapping":"Column mapping (original CSV column → internal canonical column)",
"ds_file":"File",
"ds_dropped":"Discarded rows (no patient or no variable)",
"ds_duplicates":"Repeated identical rows (kept)","ds_ignored":"Ignored columns (not in the output)",
"meth_intro":"The anonymization process was structured in the following sequential phases:",
"meth_step1_title":"Phase 1 — Dataset Normalization and Coherence",
"meth_step1_body":("Before any transformation, the coherence of the dataset was ensured:\n\n"
"- Each file's columns were mapped to the internal canonical names (`pacient`, `data`, `item`, `valor`), "
"via common aliases (`patient_id`, `variable`, `value`…) or explicit user confirmation. Any other column is discarded and does not reach the output.\n"
"- All values were read as text, without type inference: identifiers are kept exactly "
"(e.g. `0012` does not become `12` or `12.0`) and are comparable across files.\n"
"- Leading/trailing spaces were removed from identifiers, and rows without a patient or a variable were discarded.\n"
"- When there is more than one file, they were combined into a single dataset before any transformation, so "
"dates, imputation and k-anonymity are computed on all the information of each patient."),
"meth_step2_title":"Phase 2 — Date Transformation",
"meth_step2_body":("All absolute dates were replaced by an **integer minute delta** computed "
"as the difference from each patient's first visit. This preserves clinically relevant "
"temporal intervals — including intra-day, minute-level differences between observations — "
"without revealing absolute dates.\n\n"
"- First visit → value `0`\n"
"- Subsequent visits → minutes elapsed since the first visit\n"
"- If the original timestamp had no time component, the delta will be a multiple of 1440\n"
"- Original dates are not retained in any form"),
"meth_step3_title":"Phase 6 — Patient Identifier Pseudonymization",
"meth_step3_body":("The patient identifier was replaced by an **HMAC-SHA256** "
"(12 hex chars, prefix `H-`). The HMAC key is **random, secret and unique to this session**: "
"it only existed in the tool's memory during processing and is not retained anywhere. "
"Without the key the hashes cannot be recomputed from a list of candidate identifiers "
"(dictionary attack), and once the session is closed the patient → hash correspondence is "
"**unrecoverable**. The same patient receives the same hash in every file of this session.\n\n"
"Pseudonymization is applied **at the end of the process**, once the dataset is coherent, generalized and "
"k-anonymous, and only to the records that are released."),
"meth_step4_title":"Phase 3 — Missing Value Imputation",
"meth_step4_body":("Missing values in quasi-identifiers were imputed on the original values, before "
"generalization, to prevent unit equivalence classes:\n\n"
"- **Categorical**: `Desconocido`\n- **Numeric**: item median"),
"meth_step5_title":"Phase 4 — Quasi-identifier Generalization",
"meth_step5_body":("Quasi-identifier items were generalized via numeric binning or categorical grouping, "
"removing the granularity that could enable linkage attacks with external data sources. "
"Numeric values outside the defined intervals are labelled `Fuera de rango` and values that "
"cannot be read as numbers `Desconocido`; the count of each case is listed in section 5."),
"meth_step6_title":"Phase 5 — K-anonymity by Suppression",
"meth_step6_body":("The **k-anonymity** model (Sweeney, 2002) was applied:\n\n"
"1. Build each patient's signature: for every quasi-identifier, the set of distinct values it "
"takes across **all** of the patient's visits (e.g. `60-64 | 65+`)\n"
"2. Group patients by signature and identify equivalence classes with fewer than k patients\n"
"3. Remove all records of patients in non-conforming groups\n\n"
"Suppression is applied at the **full patient level** to preserve dataset coherence. Because the "
"signature covers every released value, the k guarantee also holds when a quasi-identifier "
"changes between visits."),
"cls_intro":"The user classified each item into one of the following categories:",
"cls_quasi":"Quasi-identifiers","cls_nonid":"Non-identifying (unchanged)",
"cls_quasi_desc":"Attributes that could enable re-identification through linkage with external sources. Generalized and included in k-anonymity.",
"cls_nonid_desc":"Attributes with very low re-identification potential. Retained unchanged in the output dataset.",
"gen_intro":"For each quasi-identifier, the following transformation was applied:",
"gen_type_bins":"Numeric binning (intervals)","gen_type_mapping":"Category mapping",
"gen_bins_label":"Cut points","gen_labels_label":"Resulting labels",
"gen_mapping_label":"Value mapping","gen_unmapped":"Unassigned values",
"gen_none":"No transformation (original value)",
"gen_log_non_numeric":"Non-numeric records → `Desconocido`",
"gen_log_out_of_range":"Records outside the intervals → `Fuera de rango`",
"gen_log_unmapped":"Records without a mapping → unassigned label",
"imp_intro":"Missing values were imputed for the following quasi-identifiers:",
"imp_none":"No missing values detected in quasi-identifiers. No imputation applied.",
"imp_item":"Item","imp_n":"Imputed records","imp_strat":"Strategy",
"kan_k_used":"Value of k used","kan_quasi_items":"Quasi-identifiers considered",
"kan_note":("K-anonymity guarantees that each individual in the dataset is indistinguishable "
"from at least **k−1** others. With k={k}, no individual can be singled out "
"with probability greater than 1/{k}."),
"res_before":"Before anonymization","res_after":"After anonymization",
"res_patients":"Patients","res_records":"Records",
"res_suppressed_p":"Suppressed patients","res_suppressed_r":"Suppressed records",
"res_pct":"Loss percentage",
"res_visits_min":"Min visits/patient","res_visits_max":"Max visits/patient","res_visits_mean":"Mean visits/patient",
"eq_total":"Total groups (equivalence classes)","eq_conforming":"Conforming groups (≥ k)",
"eq_suppressed":"Suppressed groups (< k)","eq_min":"Min group size",
"eq_max":"Max group size","eq_mean":"Mean group size",
"eq_dist_title":"Group size distribution","eq_size":"Group size","eq_ngroups":"No. of groups",
"eq_suppressed_detail":"Suppressed groups detail (up to 20)",
"eq_none_suppressed":"No groups suppressed. All patients satisfy the k-anonymity criterion.",
"guar_intro":("The dataset generated by this process has **three complementary layers of protection** "
"for its use in the post-Datathon InCa phase and the TSI project pilots. "
"Each layer operates independently."),
"guar_layer1_title":"Layer 1 — Technical Protection (applied transformations)",
"guar_layer1_body":("The applied transformations eliminate or obfuscate all information "
"enabling direct or indirect identification:\n\n"
"- **Patient identifier**: replaced by an HMAC-SHA256 with a secret session key that is not retained. "
"Not even a list of candidate identifiers allows the correspondence to be rebuilt.\n"
"- **Absolute dates**: destroyed and replaced by relative deltas. "
"It is impossible to infer when any observation took place.\n"
"- **Quasi-identifiers**: generalized into categories or ranges, "
"eliminating the granularity that could enable external linkage attacks.\n"
"- **K-anonymity**: mathematical guarantee that no quasi-identifier profile is unique "
"in the dataset. Each individual is indistinguishable from at least k−1 others."),
"guar_layer2_title":"Layer 2 — Presence Uncertainty (scope of the extract)",
"guar_layer2_body":("Each dataset is a bounded extract: one care line and, for the new extracts, the year 2024. "
"When the extract is a **sample** of the reference population, anyone attempting to re-identify a specific person "
"**cannot know a priori whether that person is in the dataset at all**. This uncertainty, recognized by ENISA and the "
"Article 29 Working Party as a re-identification risk mitigating factor, is independent of the technical transformations.\n\n"
"If the extract covers the whole population of the care line and period, this uncertainty does not apply and protection "
"rests on layers 1 and 3. The DPO must take this into account when assessing residual risk."),
"guar_layer3_title":"Layer 3 — Organizational Controls and Project Environment",
"guar_layer3_body":("Access to the data is governed by the **Data Use and Confidentiality Agreement** of the "
"post-Datathon InCa phase and the pilots of the TSI project “EU Health Hub – Investing in Resilient Health Systems”, "
"promoted by the Spanish Ministry of Health, WHO Regional Office for Europe and Instituto de Salud Carlos III (ISCIII):\n\n"
"- **Accredited participants**: access only for authorized participants who have signed the agreement, and until 31 May 2027 at the latest.\n"
"- **Limited purpose**: review and harmonization of variables, weighting, and development, evaluation and validation "
"of models, algorithms and analyses on care complexity and needs.\n"
"- **No re-identification or linkage**: any re-identification attempt and any combination with external sources is prohibited. "
"Crossing project datasets requires express authorization within the ISCIII secure environment.\n"
"- **Secure environment**: work takes place in the spaces enabled by ISCIII (project SharePoint and applications published on Red SARA). "
"Downloads are allowed only when essential, on corporate devices of the institution, never on personal devices "
"or cloud services or external tools, including generative AI, and local copies are deleted at the end of each task.\n"
"- **Incidents and accountability**: any information that could identify a person or any unauthorized access is reported "
"immediately to the project coordination and the team responsible for the ISCIII environment. Non-compliance may lead to "
"withdrawal of access and notification to the competent authority."),
"guar_summary_title":"Summary of Guarantees",
"guar_summary_body":("The three layers complement each other:\n\n"
"| Layer | Type | Protection provided |\n"
"|-------|------|---------------------|\n"
"| Technical | K-anonymity + session-keyed HMAC + minute delta + generalization | No profile of the selected quasi-identifiers is shared by fewer than k patients |\n"
"| Statistical | Bounded extract and, where applicable, sampling | Uncertainty about each individual's presence when the extract is a sample |\n"
"| Organizational | Data Use Agreement + ISCIII SharePoint and Red SARA + accredited participants | Access control and legal accountability |\n\n"
"**Once validated by the DPO, the resulting dataset may be added to the project's authorized environment.**"),
"con_intro":("The dataset has been processed following the standard statistical anonymization "
"techniques recognized by European data protection law and ENISA guidelines. "
"The combination of k-anonymity with the technical and organizational controls described "
"reduces the re-identification risk in the intended use context.\n\n"
"**The final assessment of residual risk rests with the DPO.**"),
"con_signed":"Technical certification of the process:",
"con_items":[
"Transformations have been applied systematically and are fully documented.",
"The value of k guarantees indistinguishability of the individuals in the final dataset with respect to the selected quasi-identifiers.",
"The full process report is available for DPO review.",
"The patient identifier has been replaced, observation dates converted to deltas, and only the 4 format columns are kept.",
"All classification decisions were made by the responsible user at the contributing centre.",
],
"con_closing":("This report was automatically generated by Local Anonymizer. "
"Classification and generalization decisions were made by the responsible user. "
"The tool does not inspect the content of non-identifying variables: "
"the responsible user must ensure they contain no free text, direct identifiers or dates. "
"The DPO must review and validate this report before the dataset is added to the project environment."),
}


def generate_markdown_report(lang, filename, col_mappings, classifications,
                              generalizations, imputation_log, metrics,
                              date_range, all_items, generalization_log=None,
                              version="?", coherence=None):
    t   = T.get(lang, T["es"])
    now = datetime.datetime.now().strftime("%d/%m/%Y %H:%M")
    k   = metrics.get("k_used", "?")
    generalization_log = generalization_log or {}
    qi_list = lambda items: ", ".join(_code(i) for i in items) if items else t["none"]

    quasi_items  = metrics.get("quasi_id_items", [])
    non_id_items = [i for i in all_items if classifications.get(i) != "quasi_id"]
    eq   = metrics.get("equivalence_classes", {})
    dist = eq.get("size_distribution", {})
    sg   = metrics.get("suppressed_groups", [])
    v_orig  = metrics.get("visits_per_patient_orig",  {})
    n_po = metrics.get("n_patients_orig",  0)
    n_pf = metrics.get("n_patients_final", 0)
    n_ro = metrics.get("n_records_orig",   0)
    n_rf = metrics.get("n_records_final",  0)
    n_sp = metrics.get("n_suppressed_patients", 0)
    pct  = metrics.get("pct_suppressed", 0.0)

    w = []
    def ln(s=""): w.append(s)

    # PORTADA
    ln(f"# {t['title']}")
    ln(f"### {t['subtitle']}")
    ln(); ln("---"); ln()
    ln(f"| | |"); ln("|---|---|")
    ln(f"| **{t['generated']}** | {now} |")
    ln(f"| **{t['tool']}** | Local Anonymizer v{version} |")
    ln(f"| **{t['project']}** | {t['project_val']} |")
    ln(f"| **{t['filename']}** | {_code(filename)} |")
    ln(f"| **{t['lang']}** | {t['lang_val']} |")
    ln(); ln("---"); ln()

    # 1. RESUM EXECUTIU
    ln(f"## {t['s_summary']}"); ln()
    ln(t["summary_intro"]); ln()
    ln(t["summary_method"]); ln()
    ln(f"**{t['summary_result']}**"); ln()
    ln(f"| | |"); ln("|---|---:|")
    ln(f"| {t['ds_patients']} | **{n_po:,}** → **{n_pf:,}** |")
    ln(f"| {t['ds_records']}  | **{n_ro:,}** → **{n_rf:,}** |")
    ln(f"| {t['kanon_label']} | **k = {k}** |")
    ln(f"| {t['kan_quasi_items']} | {qi_list(quasi_items)} |")
    ln()

    # 2. DATASET — un mapatge per fitxer (cada CCAA/fitxer pot tenir noms propis)
    canonicals = ["pacient", "data", "item", "valor"]
    ln(f"## {t['s_dataset']}"); ln()
    ln(f"**{t['ds_col_mapping']}**"); ln()
    ln(f"| {t['ds_file']} | " + " | ".join(f"`{c}`" for c in canonicals) + " |")
    ln("|---|" + "---|" * len(canonicals))
    for fname, mapping in (col_mappings or {}).items():
        ln(f"| {_code(fname)} | " + " | ".join(_code(mapping.get(c, c)) for c in canonicals) + " |")
    ln()
    ln(f"| | |"); ln("|---|---:|")
    ln(f"| {t['ds_patients']} | {n_po:,} |")
    ln(f"| {t['ds_records']}  | {n_ro:,} |")
    ln(f"| {t['ds_items']}    | {metrics.get('n_items', len(all_items))} |")
    dr = date_range or {}
    ln(f"| {t['ds_date_range']} | {dr.get('min','?')} → {dr.get('max','?')} |")
    ln(f"| {t['res_visits_min']} | {v_orig.get('min','?')} |")
    ln(f"| {t['res_visits_max']} | {v_orig.get('max','?')} |")
    ln(f"| {t['res_visits_mean']} | {v_orig.get('mean','?')} |")
    coherence = coherence or {}
    ln(f"| {t['ds_dropped']} | {coherence.get('n_dropped_rows', 0):,} |")
    ln(f"| {t['ds_duplicates']} | {coherence.get('n_duplicate_rows', 0):,} |")
    ignored = sorted({c for cols in coherence.get("ignored_columns", {}).values() for c in cols})
    ln(f"| {t['ds_ignored']} | {', '.join(_code(c) for c in ignored) if ignored else t['none']} |")
    ln()

    # 3. METODOLOGIA — en l'ordre real del pipeline: coherència, dates,
    # imputació, generalització, k-anonimitat i, al final, pseudonimització
    ln(f"## {t['s_methodology']}"); ln()
    ln(t["meth_intro"]); ln()
    for step in ["1","2","4","5","6","3"]:
        ln(f"### {t[f'meth_step{step}_title']}"); ln()
        ln(t[f"meth_step{step}_body"]); ln()

    # 4. CLASSIFICACIÓ
    ln(f"## {t['s_classification']}"); ln()
    ln(t["cls_intro"]); ln()
    if quasi_items:
        ln(f"**{t['cls_quasi']}** — {t['cls_quasi_desc']}")
        ln()
        for item in quasi_items:
            ln(f"- {_code(item)}")
        ln()
    if non_id_items:
        ln(f"**{t['cls_nonid']}** — {t['cls_nonid_desc']}")
        ln()
        for item in non_id_items[:20]:
            ln(f"- {_code(item)}")
        if len(non_id_items) > 20:
            ln(f"- _({t['and_more'].format(n=len(non_id_items) - 20)})_")
        ln()

    # 5. GENERALITZACIONS
    ln(f"## {t['s_generalizations']}"); ln()
    if not generalizations or not quasi_items:
        ln(t["gen_none"]); ln()
    else:
        ln(t["gen_intro"]); ln()
        for item in quasi_items:
            cfg = generalizations.get(item, {})
            tp  = cfg.get("type", "")
            glog = generalization_log.get(item, {})
            ln(f"### {_code(item)}"); ln()
            if tp == "bins":
                bins   = cfg.get("bins", [])
                labels = cfg.get("labels", [])
                ln(f"**{t['gen_type_bins']}**"); ln()
                ln(f"| {t['gen_bins_label']} | {t['gen_labels_label']} |"); ln("|---|---|")
                for i, lbl in enumerate(labels):
                    lo = _txt(bins[i]) if i < len(bins) else "?"
                    hi = _txt(bins[i+1]) if i+1 < len(bins) else "?"
                    ln(f"| \\[{lo}, {hi}) | {_code(lbl)} |")
                ln()
                ln(f"- {t['gen_log_non_numeric']}: **{glog.get('n_non_numeric', 0):,}**")
                ln(f"- {t['gen_log_out_of_range']}: **{glog.get('n_out_of_range', 0):,}**")
            elif tp == "mapping":
                mapping  = cfg.get("mapping", {})
                unmapped = cfg.get("unmapped_label", "Altres")
                ln(f"**{t['gen_type_mapping']}**"); ln()
                ln(f"| {t['gen_mapping_label']} | → |"); ln("|---|---|")
                for orig_v, mapped_v in sorted(mapping.items()):
                    ln(f"| {_code(orig_v)} | {_code(mapped_v)} |")
                ln(f"| _({t['gen_unmapped']})_ | {_code(unmapped)} |")
                ln()
                ln(f"- {t['gen_log_unmapped']} ({_code(unmapped)}): **{glog.get('n_unmapped', 0):,}**")
            else:
                ln(f"_{t['gen_none']}_")
            ln()

    # 6. IMPUTACIÓ
    ln(f"## {t['s_imputation']}"); ln()
    if not imputation_log:
        ln(t["imp_none"])
    else:
        ln(t["imp_intro"]); ln()
        ln(f"| {t['imp_item']} | {t['imp_n']} | {t['imp_strat']} |")
        ln("|---|---:|---|")
        for item_name, info in imputation_log.items():
            ln(f"| {_code(item_name)} | {info['n_imputed']:,} | {_txt(info['strategy'])} |")
    ln()

    # 7. K-ANONIMITAT
    ln(f"## {t['s_kanon']}"); ln()
    ln(f"- **{t['kan_k_used']}:** {k}")
    ln(f"- **{t['kan_quasi_items']}:** {qi_list(quasi_items)}")
    ln()
    note = t["kan_note"].replace("{k}", str(k))
    ln(f"> {note}"); ln()

    # 8. RESULTATS
    ln(f"## {t['s_results']}"); ln()
    ln(f"| | {t['res_before']} | {t['res_after']} |")
    ln(f"|---|---:|---:|")
    ln(f"| {t['res_patients']} | {n_po:,} | {n_pf:,} |")
    ln(f"| {t['res_records']} | {n_ro:,} | {n_rf:,} |")
    ln(f"| {t['res_suppressed_p']} | — | **{n_sp:,} ({pct}%)** |")
    ln(f"| {t['res_visits_min']} | {v_orig.get('min','?')} | — |")
    ln(f"| {t['res_visits_max']} | {v_orig.get('max','?')} | — |")
    ln(f"| {t['res_visits_mean']} | {v_orig.get('mean','?')} | — |")
    ln()

    # 9. CLASSES D'EQUIVALÈNCIA
    ln(f"## {t['s_eq_classes']}"); ln()
    ln(f"| | |"); ln(f"|---|---:|")
    ln(f"| {t['eq_total']} | {eq.get('total_groups','?')} |")
    ln(f"| {t['eq_conforming']} | {eq.get('conforming_groups','?')} |")
    ln(f"| {t['eq_suppressed']} | {eq.get('suppressed_groups_count','?')} |")
    ln(f"| {t['eq_min']} | {eq.get('min_size','?')} |")
    ln(f"| {t['eq_max']} | {eq.get('max_size','?')} |")
    ln(f"| {t['eq_mean']} | {eq.get('mean_size','?')} |")
    ln()
    ln(f"### {t['eq_dist_title']}"); ln()
    ln(f"| {t['eq_size']} | {t['eq_ngroups']} |"); ln("|---:|---:|")
    for sz, cnt in sorted(dist.items(), key=lambda x: int(x[0])):
        mark = "✅" if int(sz) >= int(k) else "❌"
        ln(f"| {mark} {sz} | {cnt} |")
    ln()
    ln(f"### {t['eq_suppressed_detail']}"); ln()
    if not sg:
        ln(f"✅ {t['eq_none_suppressed']}")
    else:
        headers = list(sg[0].keys())
        ln("| " + " | ".join(t["eq_size"] if h == "_count_" else _txt(h) for h in headers) + " |")
        ln("|" + "|".join("---" for _ in headers) + "|")
        for row in sg[:20]:
            ln("| " + " | ".join(_txt(v) for v in row.values()) + " |")
    ln()

    # 10. GARANTIES
    ln(f"## {t['s_guarantees']}"); ln()
    ln(t["guar_intro"]); ln()
    ln(f"### {t['guar_layer1_title']}"); ln()
    ln(t["guar_layer1_body"]); ln()
    ln(f"### {t['guar_layer2_title']}"); ln()
    ln(t["guar_layer2_body"]); ln()
    ln(f"### {t['guar_layer3_title']}"); ln()
    ln(t["guar_layer3_body"]); ln()
    ln(f"### {t['guar_summary_title']}"); ln()
    ln(t["guar_summary_body"]); ln()

    # 11. CONCLUSIONS
    ln(f"## {t['s_conclusions']}"); ln()
    ln(t["con_intro"]); ln()
    ln(f"**{t['con_signed']}**"); ln()
    for item in t["con_items"]:
        ln(f"- ✅ {item}")
    ln(); ln("---"); ln()
    ln(f"_{t['con_closing']}_"); ln()

    return "\n".join(w)
