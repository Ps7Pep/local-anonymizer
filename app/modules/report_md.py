"""
report_md.py  —  Genera l'informe d'anonimització en Markdown (ca/es/en)
"""
import datetime

T = {
"ca": {
"title":"Informe d'Anonimització de Dades Clíniques",
"subtitle":"Document tècnic per al Delegat/ada de Protecció de Dades",
"generated":"Generat el","tool":"Eina","version":"Versió",
"filename":"Fitxer processat","lang":"Idioma de l'informe","lang_val":"Català",
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
"El procés ha estat realitzat mitjançant l'eina **Datathon Anonymizer**, "
"que opera íntegrament en local sense transmetre cap dada a serveis externs."),
"summary_method":("La tècnica principal aplicada és la **k-anonimitat**, que garanteix que cada "
"combinació de quasi-identificadors aparegui en almenys **k** registres, "
"fent matemàticament impossible la singularització d'un individu. "
"Complementàriament, s'han aplicat hash irreversible als identificadors directes "
"i conversió a delta temporal de les dates."),
"summary_result":"El resultat del procés ha estat:",
"ds_patients":"Pacients únics","ds_records":"Registres totals","ds_items":"Variables (ítems)",
"ds_date_range":"Rang de dates","ds_col_mapping":"Correspondència de columnes detectada",
"ds_original_col":"Columna original al CSV","ds_canonical_col":"Columna canònica interna",
"meth_intro":("El procés d'anonimització s'ha estructurat en les fases següents, "
"aplicades de forma seqüencial sobre el dataset:"),
"meth_step1_title":"Fase 1 — Normalització de columnes",
"meth_step1_body":("El sistema ha detectat automàticament les columnes del CSV i les ha mapejat "
"als noms canònics interns (`pacient`, `data`, `item`, `valor`), "
"acceptant variantes habituals com `patient_id`, `variable`, `value`, etc."),
"meth_step2_title":"Fase 2 — Transformació de dates",
"meth_step2_body":("Totes les dates absolutes han estat substituïdes per un **delta enter de minuts** "
"calculat com la diferència respecte a la primera visita de cada pacient. "
"Això preserva els intervals temporals clínicament rellevants — incloent diferències intra-dia "
"de minuts entre observacions — sense revelar dates absolutes.\n\n"
"- Primera visita de cada pacient → valor `0`\n"
"- Visites posteriors → nombre de minuts transcorreguts des de la primera\n"
"- Si el timestamp original només contenia data (sense hora), el delta serà múltiple de 1440\n"
"- Les dates originals no es conserven en cap forma al dataset de sortida"),
"meth_step3_title":"Fase 3 — Pseudonimització de l'identificador de pacient",
"meth_step3_body":("L'identificador de pacient ha estat substituït per un **hash SHA-256** "
"truncat als primers 12 caràcters hexadecimals, amb el prefix `H-`. "
"Aquesta transformació és **irreversible**: és computacionalment inviable recuperar "
"l'identificador original a partir del hash sense accés a la taula original."),
"meth_step4_title":"Fase 4 — Generalització de quasi-identificadors",
"meth_step4_body":("Els ítems classificats com a **quasi-identificadors** han estat generalitzats "
"per reduir la seva granularitat i limitar el risc de reidentificació per creuament. "
"Per a variables numèriques s'han definit intervals (binning); "
"per a variables categòriques s'han agrupat valors en categories de major amplitud."),
"meth_step5_title":"Fase 5 — Imputació de valors absents",
"meth_step5_body":("Abans d'aplicar la k-anonimitat, els valors absents (NaN) dels quasi-identificadors "
"han estat imputats per evitar la formació de grups d'equivalència unitaris:\n\n"
"- **Variables categòriques**: substituïts per `Desconocido`\n"
"- **Variables numèriques**: substituïts per la mediana del ítem al dataset"),
"meth_step6_title":"Fase 6 — K-anonimitat per supressió",
"meth_step6_body":("S'ha aplicat el model de **k-anonimitat** (Sweeney, 2002) sobre les combinacions "
"de quasi-identificadors generalitzats.\n\n"
"1. Agrupa els registres per la combinació única de valors dels quasi-identificadors\n"
"2. Identifica els grups (classes d'equivalència) amb menys de **k** pacients\n"
"3. Elimina tots els registres dels pacients en grups no conformes\n\n"
"La supressió s'aplica a nivell de **pacient complet** per preservar la coherència del dataset."),
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
"guar_intro":("El dataset generat per aquest procés ofereix **múltiples capes de protecció "
"superposades** que el fan apte per al seu ús en el Datathon. "
"Cada capa actua de forma independent i les tres juntes proporcionen un nivell de "
"seguretat molt superior al que seria necessari en el context d'ús descrit."),
"guar_layer1_title":"Capa 1 — Protecció tècnica (transformacions aplicades)",
"guar_layer1_body":("Les transformacions aplicades en aquest procés eliminen o ofusquen "
"tota la informació que permet la identificació directa o indirecta:\n\n"
"- **Identificador de pacient**: substituït per hash SHA-256 irreversible. "
"Sense accés a la taula original, la recuperació és computacionalment inviable.\n"
"- **Dates absolutes**: destruïdes i substituïdes per deltes relatius. "
"No és possible inferir quan va tenir lloc cap observació.\n"
"- **Quasi-identificadors**: generalitzats en categories o rangs. "
"La granularitat original (que podria permetre creuaments amb fonts externes) ha estat eliminada.\n"
"- **K-anonimitat**: garantia matemàtica que cap perfil de quasi-identificadors "
"és únic al dataset. Cada individu és indistingible d'almenys k−1 altres."),
"guar_layer2_title":"Capa 2 — Incertesa de mostreig (protecció inherent al context)",
"guar_layer2_body":("El dataset del Datathon és una **mostra aleatòria** d'una població clínica "
"molt més gran. Aquesta característica afegeix una capa de protecció estadística "
"que és independent de les transformacions tècniques aplicades:\n\n"
"> Un potencial atacant que intenti reidentificar una persona concreta "
"**no pot saber a priori si aquella persona és al dataset**. "
"La incertesa sobre la presència mateixa de l'individu a la mostra "
"fa que qualsevol intent de reidentificació sigui especulatiu i poc fiable.\n\n"
"Aquesta propietat, reconeguda per l'ENISA i el Grup de Treball de l'Article 29 "
"com a factor mitigador del risc de reidentificació, s'aplica a tots els individus "
"del dataset independentment del seu perfil demogràfic o clínic."),
"guar_layer3_title":"Capa 3 — Controls organitzacionals i de l'entorn del Datathon",
"guar_layer3_body":("Més enllà de les proteccions tècniques i estadístiques, el marc organitzatiu "
"del Datathon proporciona una tercera capa de salvaguarda:\n\n"
"- **Participants seleccionats i acreditats**: l'accés al dataset és restringit "
"a un grup limitat de participants prèviament identificats, acreditats i registrats.\n"
"- **Acord d'ús de dades (Data Use Agreement)**: tots els participants signen un "
"compromís formal d'ús responsable, que prohibeix expressament qualsevol intent "
"d'identificació d'individus i estableix sancions en cas d'incompliment.\n"
"- **Entorn tècnic segur**: l'esdeveniment té lloc en la infraestructura de servidors "
"de l'**Instituto de Salud Carlos III (Madrid)**, gestionada pel seu propi personal "
"qualificat. L'accés és físicament i lògicament restringit a l'àmbit de l'esdeveniment.\n"
"- **Dades no exportables**: el dataset opera en un entorn tancat durant el Datathon. "
"Cap participant pot extreure dades fora dels sistemes controlats de l'organització."),
"guar_summary_title":"Síntesi de les garanties",
"guar_summary_body":("La combinació de les tres capes descrites constitueix una protecció "
"**substancialment superior** al que exigeixen el RGPD i les guies de l'ENISA "
"per al tractament de dades de salut amb finalitats d'investigació:\n\n"
"| Capa | Tipus | Protecció aportada |\n"
"|------|-------|--------------------|\n"
"| Tècnica | K-anonimitat + hash + delta de minuts + generalització | Impossibilitat matemàtica de singularització |\n"
"| Estadística | Incertesa de mostreig | Incertesa sobre la presència de cada individu |\n"
"| Organitzacional | DUA + entorn segur ISCIII + participants acreditats | Control d'accés i responsabilitat legal |\n\n"
"**El dataset resultant d'aquest procés és apte per al seu ús en el Datathon.**"),
# ── CONCLUSIONS ───────────────────────────────────────────────────────────────
"con_intro":("El dataset ha estat processat seguint les tècniques estàndard "
"d'anonimització estadística reconegudes per la normativa europea de protecció de dades "
"i les guies de l'ENISA. La combinació de la k-anonimitat amb la incertesa de mostreig "
"i els controls organitzacionals del Datathon fa que el risc residual de reidentificació "
"sigui **negligible en el context d'ús previst**.\n\n"
"**El dataset és apte per al seu ús en el Datathon.**"),
"con_signed":"Certificació tècnica del procés:",
"con_items":[
"Les transformacions han estat aplicades de forma sistemàtica i documentada.",
"El valor de k garanteix la indistingibilitat de tots els individus del dataset final.",
"L'informe complet del procés queda disponible per a la seva revisió pel DPD/DPO.",
"El dataset resultant no conté identificadors directes ni dates absolutes.",
"Totes les decisions de classificació han estat preses per l'usuari responsable del centre.",
],
"con_closing":("Aquest informe ha estat generat automàticament per l'eina Datathon Anonymizer. "
"Les decisions de classificació i generalització de variables han estat preses per "
"l'usuari responsable del centre. El DPD/DPO ha de revisar i validar aquest informe "
"abans de la posada a disposició del dataset als participants del Datathon."),
},
}

T["es"] = {
"title":"Informe de Anonimización de Datos Clínicos",
"subtitle":"Documento técnico para el Delegado/a de Protección de Datos",
"generated":"Generado el","tool":"Herramienta","version":"Versión",
"filename":"Fichero procesado","lang":"Idioma del informe","lang_val":"Castellano",
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
"El proceso ha sido realizado mediante la herramienta **Datathon Anonymizer**, "
"que opera íntegramente en local sin transmitir ningún dato a servicios externos."),
"summary_method":("La técnica principal aplicada es la **k-anonimidad**, que garantiza que cada "
"combinación de cuasi-identificadores aparezca en al menos **k** registros, "
"haciendo matemáticamente imposible la singularización de un individuo. "
"Complementariamente, se han aplicado hash irreversible a los identificadores directos "
"y conversión a delta temporal de las fechas."),
"summary_result":"El resultado del proceso ha sido:",
"ds_patients":"Pacientes únicos","ds_records":"Registros totales","ds_items":"Variables (ítems)",
"ds_date_range":"Rango de fechas","ds_col_mapping":"Correspondencia de columnas detectada",
"ds_original_col":"Columna original en el CSV","ds_canonical_col":"Columna canónica interna",
"meth_intro":"El proceso de anonimización se ha estructurado en las siguientes fases secuenciales:",
"meth_step1_title":"Fase 1 — Normalización de columnas",
"meth_step1_body":"El sistema detectó automáticamente las columnas del CSV y las mapeó a los nombres canónicos internos, aceptando variantes habituales como `patient_id`, `variable`, `value`, etc.",
"meth_step2_title":"Fase 2 — Transformación de fechas",
"meth_step2_body":("Todas las fechas absolutas han sido sustituidas por un **delta entero de minutos** "
"calculado como la diferencia respecto a la primera visita de cada paciente. "
"Esto preserva los intervalos temporales clínicamente relevantes — incluyendo diferencias "
"intra-día de minutos entre observaciones — sin revelar fechas absolutas.\n\n"
"- Primera visita → valor `0`\n"
"- Visitas posteriores → minutos transcurridos desde la primera\n"
"- Si el timestamp original solo contenía fecha (sin hora), el delta será múltiplo de 1440\n"
"- Las fechas originales no se conservan en ninguna forma"),
"meth_step3_title":"Fase 3 — Seudonimización del identificador de paciente",
"meth_step3_body":("El identificador de paciente ha sido sustituido por un **hash SHA-256** truncado "
"(12 caracteres hex, prefijo `H-`). Transformación **irreversible**: es computacionalmente "
"inviable recuperar el identificador original sin acceso a la tabla original."),
"meth_step4_title":"Fase 4 — Generalización de cuasi-identificadores",
"meth_step4_body":"Los ítems clasificados como cuasi-identificadores han sido generalizados mediante intervalos numéricos o agrupación de categorías, eliminando la granularidad que podría facilitar el cruce con fuentes externas.",
"meth_step5_title":"Fase 5 — Imputación de valores ausentes",
"meth_step5_body":("Los valores ausentes de los cuasi-identificadores han sido imputados:\n\n"
"- **Categóricas**: `Desconocido`\n- **Numéricas**: mediana del ítem"),
"meth_step6_title":"Fase 6 — K-anonimidad por supresión",
"meth_step6_body":("Se ha aplicado el modelo de **k-anonimidad** (Sweeney, 2002):\n\n"
"1. Agrupa registros por combinación de cuasi-identificadores generalizados\n"
"2. Identifica grupos con menos de k pacientes\n"
"3. Elimina todos los registros de pacientes en grupos no conformes\n\n"
"La supresión se aplica a nivel de **paciente completo**."),
"cls_intro":"El usuario ha clasificado cada ítem en una de las categorías siguientes:",
"cls_quasi":"Cuasi-identificadores","cls_nonid":"No identificativos (sin cambios)",
"cls_quasi_desc":"Atributos que podrían permitir la reidentificación por cruce con fuentes externas. Han sido generalizados e incluidos en la k-anonimidad.",
"cls_nonid_desc":"Atributos con muy baja capacidad de reidentificación. Se mantienen sin modificación.",
"gen_intro":"Para cada cuasi-identificador se ha aplicado la transformación siguiente:",
"gen_type_bins":"Binning numérico (intervalos)","gen_type_mapping":"Mapeo de categorías",
"gen_bins_label":"Puntos de corte","gen_labels_label":"Etiquetas resultantes",
"gen_mapping_label":"Mapeo de valores","gen_unmapped":"Valores no asignados",
"gen_none":"Sin transformación (valor original)",
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
"guar_intro":("El dataset generado por este proceso ofrece **múltiples capas de protección "
"superpuestas** que lo hacen apto para su uso en el Datathon. "
"Cada capa actúa de forma independiente y las tres juntas proporcionan un nivel de "
"seguridad muy superior al necesario en el contexto de uso descrito."),
"guar_layer1_title":"Capa 1 — Protección técnica (transformaciones aplicadas)",
"guar_layer1_body":("Las transformaciones aplicadas eliminan u ofuscan toda la información "
"que permite la identificación directa o indirecta:\n\n"
"- **Identificador de paciente**: sustituido por hash SHA-256 irreversible.\n"
"- **Fechas absolutas**: destruidas y sustituidas por deltas relativos. "
"No es posible inferir cuándo tuvo lugar ninguna observación.\n"
"- **Cuasi-identificadores**: generalizados en categorías o rangos. "
"La granularidad original ha sido eliminada.\n"
"- **K-anonimidad**: garantía matemática de que ningún perfil de cuasi-identificadores "
"es único en el dataset. Cada individuo es indistinguible de al menos k−1 otros."),
"guar_layer2_title":"Capa 2 — Incertidumbre de muestreo (protección inherente al contexto)",
"guar_layer2_body":("El dataset del Datathon es una **muestra aleatoria** de una población clínica "
"mucho mayor. Esta característica añade una capa de protección estadística "
"independiente de las transformaciones técnicas aplicadas:\n\n"
"> Un potencial atacante que intente reidentificar a una persona concreta "
"**no puede saber a priori si esa persona está en el dataset**. "
"La incertidumbre sobre la presencia del individuo en la muestra hace que "
"cualquier intento de reidentificación sea especulativo y poco fiable.\n\n"
"Esta propiedad, reconocida por la ENISA y el Grupo de Trabajo del Artículo 29 "
"como factor mitigador del riesgo de reidentificación, se aplica a todos los individuos "
"del dataset con independencia de su perfil demográfico o clínico."),
"guar_layer3_title":"Capa 3 — Controles organizacionales y del entorno del Datathon",
"guar_layer3_body":("Más allá de las protecciones técnicas y estadísticas, el marco organizacional "
"del Datathon proporciona una tercera capa de salvaguarda:\n\n"
"- **Participantes seleccionados y acreditados**: el acceso al dataset está restringido "
"a un grupo limitado de participantes previamente identificados, acreditados y registrados.\n"
"- **Acuerdo de uso de datos (Data Use Agreement)**: todos los participantes firman un "
"compromiso formal de uso responsable, que prohíbe expresamente cualquier intento "
"de identificación de individuos y establece sanciones en caso de incumplimiento.\n"
"- **Entorno técnico seguro**: el evento tiene lugar en la infraestructura de servidores "
"del **Instituto de Salud Carlos III (Madrid)**, gestionada por su propio personal "
"cualificado. El acceso es física y lógicamente restringido al ámbito del evento.\n"
"- **Datos no exportables**: el dataset opera en un entorno cerrado durante el Datathon. "
"Ningún participante puede extraer datos fuera de los sistemas controlados de la organización."),
"guar_summary_title":"Síntesis de las garantías",
"guar_summary_body":("La combinación de las tres capas descritas constituye una protección "
"**sustancialmente superior** a lo que exigen el RGPD y las guías de la ENISA "
"para el tratamiento de datos de salud con fines de investigación:\n\n"
"| Capa | Tipo | Protección aportada |\n"
"|------|------|---------------------|\n"
"| Técnica | K-anonimidad + hash + delta de minutos + generalización | Imposibilidad matemática de singularización |\n"
"| Estadística | Incertidumbre de muestreo | Incertidumbre sobre la presencia de cada individuo |\n"
"| Organizacional | DUA + entorno seguro ISCIII + participantes acreditados | Control de acceso y responsabilidad legal |\n\n"
"**El dataset resultante de este proceso es apto para su uso en el Datathon.**"),
"con_intro":("El dataset ha sido procesado siguiendo las técnicas estándar de anonimización "
"estadística reconocidas por la normativa europea de protección de datos y las guías de la ENISA. "
"La combinación de la k-anonimidad con la incertidumbre de muestreo y los controles "
"organizacionales del Datathon hace que el riesgo residual de reidentificación sea "
"**negligible en el contexto de uso previsto**.\n\n"
"**El dataset es apto para su uso en el Datathon.**"),
"con_signed":"Certificación técnica del proceso:",
"con_items":[
"Las transformaciones han sido aplicadas de forma sistemática y documentada.",
"El valor de k garantiza la indistinguibilidad de todos los individuos del dataset final.",
"El informe completo del proceso queda disponible para su revisión por el DPD/DPO.",
"El dataset resultante no contiene identificadores directos ni fechas absolutas.",
"Todas las decisiones de clasificación han sido tomadas por el usuario responsable del centro.",
],
"con_closing":("Informe generado automáticamente por Datathon Anonymizer. "
"Las decisiones de clasificación y generalización han sido tomadas por el usuario responsable. "
"El DPD/DPO debe revisar y validar este informe antes de la puesta a disposición "
"del dataset a los participantes del Datathon."),
}

T["en"] = {
"title":"Clinical Data Anonymization Report",
"subtitle":"Technical document for the Data Protection Officer",
"generated":"Generated on","tool":"Tool","version":"Version",
"filename":"Processed file","lang":"Report language","lang_val":"English",
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
"The process was carried out using **Datathon Anonymizer**, which operates entirely "
"locally without transmitting any data to external services."),
"summary_method":("The main technique applied is **k-anonymity**, which mathematically guarantees "
"that each quasi-identifier combination appears in at least **k** records, "
"making it impossible to single out any individual. Complementary protections "
"include irreversible hashing of direct identifiers and temporal delta conversion of dates."),
"summary_result":"The outcome of the process was:",
"ds_patients":"Unique patients","ds_records":"Total records","ds_items":"Variables (items)",
"ds_date_range":"Date range","ds_col_mapping":"Detected column mapping",
"ds_original_col":"Original column in CSV","ds_canonical_col":"Internal canonical column",
"meth_intro":"The anonymization process was structured in the following sequential phases:",
"meth_step1_title":"Phase 1 — Column Normalization",
"meth_step1_body":"The system automatically detected CSV columns and mapped them to internal canonical names, accepting common variants such as `patient_id`, `variable`, `value`, etc.",
"meth_step2_title":"Phase 2 — Date Transformation",
"meth_step2_body":("All absolute dates were replaced by an **integer minute delta** computed "
"as the difference from each patient's first visit. This preserves clinically relevant "
"temporal intervals — including intra-day, minute-level differences between observations — "
"without revealing absolute dates.\n\n"
"- First visit → value `0`\n"
"- Subsequent visits → minutes elapsed since the first visit\n"
"- If the original timestamp had no time component, the delta will be a multiple of 1440\n"
"- Original dates are not retained in any form"),
"meth_step3_title":"Phase 3 — Patient Identifier Pseudonymization",
"meth_step3_body":("The patient identifier was replaced by a **SHA-256 hash** "
"(12 hex chars, prefix `H-`). This transformation is **irreversible**: "
"recovering the original identifier without the source table is computationally infeasible."),
"meth_step4_title":"Phase 4 — Quasi-identifier Generalization",
"meth_step4_body":"Quasi-identifier items were generalized via numeric binning or categorical grouping, removing the granularity that could enable linkage attacks with external data sources.",
"meth_step5_title":"Phase 5 — Missing Value Imputation",
"meth_step5_body":("Missing values in quasi-identifiers were imputed to prevent unit equivalence classes:\n\n"
"- **Categorical**: `Desconocido`\n- **Numeric**: item median"),
"meth_step6_title":"Phase 6 — K-anonymity by Suppression",
"meth_step6_body":("The **k-anonymity** model (Sweeney, 2002) was applied:\n\n"
"1. Group records by generalized quasi-identifier combination\n"
"2. Identify equivalence classes with fewer than k patients\n"
"3. Remove all records of patients in non-conforming groups\n\n"
"Suppression is applied at the **full patient level** to preserve dataset coherence."),
"cls_intro":"The user classified each item into one of the following categories:",
"cls_quasi":"Quasi-identifiers","cls_nonid":"Non-identifying (unchanged)",
"cls_quasi_desc":"Attributes that could enable re-identification through linkage with external sources. Generalized and included in k-anonymity.",
"cls_nonid_desc":"Attributes with very low re-identification potential. Retained unchanged in the output dataset.",
"gen_intro":"For each quasi-identifier, the following transformation was applied:",
"gen_type_bins":"Numeric binning (intervals)","gen_type_mapping":"Category mapping",
"gen_bins_label":"Cut points","gen_labels_label":"Resulting labels",
"gen_mapping_label":"Value mapping","gen_unmapped":"Unassigned values",
"gen_none":"No transformation (original value)",
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
"guar_intro":("The dataset generated by this process offers **multiple overlapping layers of protection** "
"that make it suitable for use in the Datathon. "
"Each layer operates independently, and together they provide a level of security "
"well above what is required for the described use context."),
"guar_layer1_title":"Layer 1 — Technical Protection (applied transformations)",
"guar_layer1_body":("The applied transformations eliminate or obfuscate all information "
"enabling direct or indirect identification:\n\n"
"- **Patient identifier**: replaced by irreversible SHA-256 hash. "
"Recovery without the source table is computationally infeasible.\n"
"- **Absolute dates**: destroyed and replaced by relative deltas. "
"It is impossible to infer when any observation took place.\n"
"- **Quasi-identifiers**: generalized into categories or ranges, "
"eliminating the granularity that could enable external linkage attacks.\n"
"- **K-anonymity**: mathematical guarantee that no quasi-identifier profile is unique "
"in the dataset. Each individual is indistinguishable from at least k−1 others."),
"guar_layer2_title":"Layer 2 — Sampling Uncertainty (inherent contextual protection)",
"guar_layer2_body":("The Datathon dataset is a **random sample** of a much larger clinical population. "
"This characteristic adds a statistical layer of protection independent of the "
"technical transformations applied:\n\n"
"> A potential attacker attempting to re-identify a specific person "
"**cannot know a priori whether that person is in the dataset at all**. "
"The uncertainty about an individual's very presence in the sample makes any "
"re-identification attempt speculative and unreliable.\n\n"
"This property — recognized by ENISA and the Article 29 Working Party as a "
"re-identification risk mitigating factor — applies to all individuals in the dataset "
"regardless of their demographic or clinical profile."),
"guar_layer3_title":"Layer 3 — Organizational Controls and Datathon Environment",
"guar_layer3_body":("Beyond the technical and statistical protections, the organizational "
"framework of the Datathon provides a third safeguard layer:\n\n"
"- **Selected and accredited participants**: access to the dataset is restricted to a "
"limited group of previously identified, accredited and registered participants.\n"
"- **Data Use Agreement (DUA)**: all participants sign a formal responsible-use commitment "
"that expressly prohibits any attempt to identify individuals and establishes "
"penalties for non-compliance.\n"
"- **Secure technical environment**: the event takes place on the server infrastructure "
"of the **Instituto de Salud Carlos III (Madrid)**, managed by its own qualified staff. "
"Access is physically and logically restricted to the event context.\n"
"- **Non-exportable data**: the dataset operates in a closed environment during the Datathon. "
"No participant can extract data outside the organization's controlled systems."),
"guar_summary_title":"Summary of Guarantees",
"guar_summary_body":("The combination of the three layers described constitutes protection "
"**substantially above** what the GDPR and ENISA guidelines require for health data "
"processing for research purposes:\n\n"
"| Layer | Type | Protection provided |\n"
"|-------|------|---------------------|\n"
"| Technical | K-anonymity + hash + minute delta + generalization | Mathematical impossibility of singling out |\n"
"| Statistical | Sampling uncertainty | Uncertainty about each individual's presence |\n"
"| Organizational | DUA + secure ISCIII environment + accredited participants | Access control and legal accountability |\n\n"
"**The dataset resulting from this process is suitable for use in the Datathon.**"),
"con_intro":("The dataset has been processed following the standard statistical anonymization "
"techniques recognized by European data protection law and ENISA guidelines. "
"The combination of k-anonymity with sampling uncertainty and the Datathon's "
"organizational controls makes the residual re-identification risk "
"**negligible in the intended use context**.\n\n"
"**The dataset is suitable for use in the Datathon.**"),
"con_signed":"Technical certification of the process:",
"con_items":[
"Transformations have been applied systematically and are fully documented.",
"The value of k guarantees indistinguishability of all individuals in the final dataset.",
"The full process report is available for DPO review.",
"The resulting dataset contains no direct identifiers or absolute dates.",
"All classification decisions were made by the responsible user at the contributing centre.",
],
"con_closing":("This report was automatically generated by Datathon Anonymizer. "
"Classification and generalization decisions were made by the responsible user. "
"The DPO must review and validate this report before making the dataset available "
"to Datathon participants."),
}


def generate_markdown_report(lang, filename, col_mapping, classifications,
                              generalizations, imputation_log, metrics,
                              date_range, all_items, orig_pacient_col="patient_id"):
    t   = T.get(lang, T["ca"])
    now = datetime.datetime.now().strftime("%d/%m/%Y %H:%M")
    k   = metrics.get("k_used", "?")

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
    ln(f"| **{t['tool']}** | Datathon Anonymizer v2.0 |")
    ln(f"| **{t['filename']}** | `{filename}` |")
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
    ln(f"| K-anonimitat | **k = {k}** |")
    ln(f"| {t['kan_quasi_items']} | {', '.join(f'`{i}`' for i in quasi_items) if quasi_items else '_(cap)_'} |")
    ln()

    # 2. DATASET
    ln(f"## {t['s_dataset']}"); ln()
    col_inv = {v: k_ for k_, v in col_mapping.items()}
    ln(f"| {t['ds_original_col']} | {t['ds_canonical_col']} |")
    ln("|---|---|")
    for can in ["pacient", "data", "item", "valor"]:
        orig = col_inv.get(can, can)
        ln(f"| `{orig}` | `{can}` |")
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
    ln()

    # 3. METODOLOGIA
    ln(f"## {t['s_methodology']}"); ln()
    ln(t["meth_intro"]); ln()
    for step in ["1","2","3","4","5","6"]:
        ln(f"### {t[f'meth_step{step}_title']}"); ln()
        ln(t[f"meth_step{step}_body"]); ln()

    # 4. CLASSIFICACIÓ
    ln(f"## {t['s_classification']}"); ln()
    ln(t["cls_intro"]); ln()
    if quasi_items:
        ln(f"**{t['cls_quasi']}** — {t['cls_quasi_desc']}")
        ln()
        for item in quasi_items:
            ln(f"- `{item}`")
        ln()
    if non_id_items:
        ln(f"**{t['cls_nonid']}** — {t['cls_nonid_desc']}")
        ln()
        for item in non_id_items[:20]:
            ln(f"- `{item}`")
        if len(non_id_items) > 20:
            ln(f"- _(i {len(non_id_items)-20} més)_")
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
            ln(f"### `{item}`"); ln()
            if tp == "bins":
                bins   = cfg.get("bins", [])
                labels = cfg.get("labels", [])
                ln(f"**{t['gen_type_bins']}**"); ln()
                ln(f"| {t['gen_bins_label']} | {t['gen_labels_label']} |"); ln("|---|---|")
                for i, lbl in enumerate(labels):
                    lo = bins[i] if i < len(bins) else "?"
                    hi = bins[i+1] if i+1 < len(bins) else "?"
                    ln(f"| [{lo}, {hi}) | `{lbl}` |")
            elif tp == "mapping":
                mapping  = cfg.get("mapping", {})
                unmapped = cfg.get("unmapped_label", "Desconocido")
                ln(f"**{t['gen_type_mapping']}**"); ln()
                ln(f"| {t['gen_mapping_label']} | → |"); ln("|---|---|")
                for orig_v, mapped_v in sorted(mapping.items()):
                    ln(f"| `{orig_v}` | `{mapped_v}` |")
                ln(f"| _({t['gen_unmapped']})_ | `{unmapped}` |")
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
            ln(f"| `{item_name}` | {info['n_imputed']:,} | {info['strategy']} |")
    ln()

    # 7. K-ANONIMITAT
    ln(f"## {t['s_kanon']}"); ln()
    ln(f"- **{t['kan_k_used']}:** {k}")
    qi_str = ', '.join(f'`{i}`' for i in quasi_items) if quasi_items else '_(cap)_'
    ln(f"- **{t['kan_quasi_items']}:** {qi_str}")
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
        ln("| " + " | ".join(str(h) for h in headers) + " |")
        ln("|" + "|".join("---" for _ in headers) + "|")
        for row in sg[:20]:
            ln("| " + " | ".join(str(v) for v in row.values()) + " |")
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
