from django.shortcuts import render
from django.db import connections
from django.http import HttpResponse
import logging


def katalog(request):
    base_query = """
        SELECT 
            dataset_list.data_set,
            dataset_list.data_set_name, 
            dataset_list.description AS dataset_description, 
            dataset_list.rights_holder AS dataset_rights_holder, 
            dataset_list.subject AS dataset_subject, 
            dataset_list.complete AS dataset_complete,
            COALESCE(datasource_list.data_source_name, dataset_list.data_source) AS dataset_data_source,
            STRING_AGG(DISTINCT dataclass_list.data_class, '||') AS data_class_ids,
            STRING_AGG(DISTINCT dataclass_list.data_class_name, '||') AS data_class_names,
            STRING_AGG(DISTINCT dataclass_list.subject, '||') AS dataclass_subjects,
            STRING_AGG(DISTINCT dataclass_list.description, '||') AS dataclass_descriptions,
            STRING_AGG(DISTINCT dataclass_list.complete, '||') AS dataclass_complete,
            STRING_AGG(DISTINCT dataclass_list.file_extension, '||') AS dataclass_file_extensions,
            STRING_AGG(DISTINCT dataclass_list.repository, '||') AS dataclass_repositories,
            COALESCE(
                STRING_AGG(
                    DISTINCT 
                        db_table_list.db_table || ':' || 
                        COALESCE(db_table_list.data_class, '') || ':' || 
                        COALESCE(db_table_list.db_table_name, '') || ':' ||
                        COALESCE(REPLACE(db_table_list.description, ':', ' - '), ''),
                    '||'
                ),
                ''
            ) AS db_table_info
        FROM metadata.dataset_list
        LEFT JOIN metadata.dataclass_list ON dataclass_list.data_set = dataset_list.data_set
        LEFT JOIN metadata.db_table_list ON db_table_list.data_class = dataclass_list.data_class
        LEFT JOIN metadata.datasource_list ON dataset_list.data_source = datasource_list.data_source
        GROUP BY 
            dataset_list.data_set, 
            dataset_list.data_set_name,
            dataset_list.description,
            dataset_list.rights_holder,
            dataset_list.subject,
            dataset_list.complete,
            datasource_list.data_source_name
    """

    try:
        with connections['warehouse_db'].cursor() as cursor:
            cursor.execute(base_query)
            columns = [col[0] for col in cursor.description]
            datasets = []
            subject_tags = set()
            rights_holders = set()
            data_sources = set()

            for row in cursor.fetchall():
                dataset = dict(zip(columns, row))

                subject_tags_list = [tag.strip() for tag in (dataset.get('dataset_subject') or '').split(',') if tag.strip()]
                subject_tags.update(subject_tags_list)

                if dataset.get('dataset_rights_holder'):
                    rights_holders.add(dataset['dataset_rights_holder'])

                if dataset.get('dataset_data_source'):
                    data_sources.add(dataset['dataset_data_source'])

                data_class_ids_list = [s.strip() for s in (dataset.get('data_class_ids') or '').split('||') if s.strip()]
                data_class_names_list = [s.strip() for s in (dataset.get('data_class_names') or '').split('||') if s.strip()]
                dataclass_subjects_list = [s.strip() for s in (dataset.get('dataclass_subjects') or '').split('||') if s.strip()]
                dataclass_descriptions_list = [s.strip() for s in (dataset.get('dataclass_descriptions') or '').split('||') if s.strip()]
                dataclass_complete_list = [s.strip() for s in (dataset.get('dataclass_complete') or '').split('||') if s.strip()]
                dataclass_file_extensions_list = [s.strip() for s in (dataset.get('dataclass_file_extensions') or '').split('||') if s.strip()]
                dataclass_repositories_list = [s.strip() for s in (dataset.get('dataclass_repositories') or '').split('||') if s.strip()]

                db_table_info_list = [s.strip() for s in (dataset.get('db_table_info') or '').split('||') if s.strip()]

                data_classes = []
                has_tables = False

                for i, data_class_id in enumerate(data_class_ids_list):
                    data_class_name = data_class_names_list[i] if i < len(data_class_names_list) else ""
                    data_class_subject = dataclass_subjects_list[i] if i < len(dataclass_subjects_list) else ""
                    data_class_description = dataclass_descriptions_list[i] if i < len(dataclass_descriptions_list) else ""
                    data_class_complete = dataclass_complete_list[i] if i < len(dataclass_complete_list) else ""
                    data_class_file_extension = dataclass_file_extensions_list[i] if i < len(dataclass_file_extensions_list) else ""
                    data_class_repository = dataclass_repositories_list[i] if i < len(dataclass_repositories_list) else ""

                    has_classes = bool(data_class_repository)
                    dataclass_columns = []

                    try:
                        with connections['warehouse_db'].cursor() as col_cursor:
                            col_cursor.execute(""" 
                                SELECT col_order, col_name 
                                FROM metadata.dataclass_table_schemes 
                                WHERE data_class = %s 
                                ORDER BY col_order 
                            """, [data_class_id])
                            dataclass_columns = [{"col_order": row[0], "col_name": row[1]} for row in col_cursor.fetchall()]
                    except Exception as e:
                        logging.getLogger(__name__).error(f"Chyba při načítání sloupců pro třídu {data_class_id}: {str(e)}")

                    db_tables = []
                    for table_info in db_table_info_list:
                        parts = table_info.split(':', 3)
                        if len(parts) == 4:
                            table_id, table_class_id, table_name, table_description = parts

                            variables = []
                            try:
                                with connections['warehouse_db'].cursor() as var_cursor:
                                    var_cursor.execute(""" 
                                        SELECT var, var_name, vocabulary, var_order, key_db, type_db 
                                        FROM metadata.db_table_schemes 
                                        WHERE db_table = %s 
                                        ORDER BY var_order 
                                    """, [table_id])
                                    variables = [{
                                        "var": row[0],
                                        "var_name": row[1],
                                        "vocabulary": row[2] or "",
                                        "var_order": row[3] or "",
                                        "key_db": row[4] or "",
                                        "type_db": row[5] or ""
                                    } for row in var_cursor.fetchall()]
                            except Exception as e:
                                logging.getLogger(__name__).error(
                                    f"Chyba při načítání proměnných pro tabulku {table_id}: {str(e)}"
                                )

                            db_tables.append({
                                "id": table_id,
                                "name": table_name,
                                "description": table_description,
                                "data_class_id": table_class_id,
                                "variables": variables
                            })

                    has_tables = has_tables or bool(db_tables)

                    data_classes.append({
                        "id": data_class_id,
                        "name": data_class_name,
                        "subject": data_class_subject,
                        "description": data_class_description,
                        "complete": data_class_complete.lower() == 'ano',
                        "file_extension": data_class_file_extension,
                        "repository": data_class_repository,
                        "columns": dataclass_columns,
                        "db_tables": db_tables,
                        "has_tables": bool(db_tables),
                        "has_classes": has_classes
                    })

                dataset_status = "has_tables" if has_tables else "has_classes" if any(
                    dc["has_classes"] for dc in data_classes) else "no_data"

                dataset_has_classes = any(dc["has_classes"] for dc in data_classes)

                datasets.append({
                    "data_set": dataset.get("data_set", ""),
                    "data_set_name": dataset.get("data_set_name", ""),
                    "description": dataset.get("dataset_description", ""),
                    "rights_holder": dataset.get("dataset_rights_holder", ""),
                    "subject_tags": subject_tags_list,
                    "data_source": dataset.get("dataset_data_source", ""),
                    "complete": dataset.get("dataset_complete", "") == "ano",
                    "data_class_names": ", ".join(dc["name"] for dc in data_classes),
                    "data_classes": data_classes,
                    "db_tables": db_tables,
                    "has_tables": has_tables,
                    "has_classes": dataset_has_classes,
                    "status": dataset_status
                })

    except Exception as e:
        logging.getLogger(__name__).error(f"Chyba při načítání dat katalogu: {str(e)}")
        return HttpResponse("Chyba při načítání dat katalogu.", status=500)

    return render(request, "warehouse/katalog.html", {
        "datasets": datasets,
        "subject_tags": sorted(subject_tags),
        "rights_holders": sorted(rights_holders),
        "data_sources": sorted(data_sources),
    })
