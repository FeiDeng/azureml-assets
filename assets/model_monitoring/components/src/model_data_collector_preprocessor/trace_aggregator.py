# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.
"""Internal logic for Trace Aggregator step of Gen AI preprocessor component."""


from pyspark.sql import DataFrame, Row
from pyspark.sql.functions import collect_list, struct
from typing import List

from model_data_collector_preprocessor.span_tree_utils import SpanTree, SpanTreeNode
from assets.model_monitoring.components.src.model_data_collector_preprocessor.genai_preprocessor_df_schemas import (
    _get_preprocessed_span_logs_df_schema,
    _get_aggregated_trace_log_spark_df_schema
)


def _construct_aggregated_trace_entry(span_tree: SpanTree) -> tuple:
    """Build an aggregated trace tuple for RDD from a span tree."""
    trace_schema_names = _get_aggregated_trace_log_spark_df_schema().fieldNames()
    span_dict = span_tree.root_span.span_row.asDict()
    
    data = {key_name: span_dict.get(key_name, None) for key_name in trace_schema_names}
    data['root_span'] = span_tree.to_json_str()
    return tuple(entry for entry in data.values())


def _construct_span_tree(span_rows: List[Row]) -> SpanTree:
    """Build a span tree from the raw span rows."""
    span_list = [SpanTreeNode(row) for row in span_rows]
    tree = SpanTree(span_list)
    return tree


def _aggregate_span_logs_to_trace_logs(grouped_row: Row):
    """Aggregate grouped span logs into trace logs."""
    tree = _construct_span_tree(grouped_row.span_rows)
    return _construct_aggregated_trace_entry(tree)


def process_spans_into_aggregated_traces(span_logs: DataFrame) -> DataFrame:
    """Group span logs into aggregated trace logs."""
    print("Processing spans into aggregated traces...")

    grouped_spans_df = span_logs.groupBy('trace_id').agg(
        collect_list(
            struct(_get_preprocessed_span_logs_df_schema().fieldNames())
        ).alias('span_rows')
    )
    all_aggregated_traces = grouped_spans_df \
        .rdd \
        .map(lambda x: _aggregate_span_logs_to_trace_logs(x)) \
        .toDF(_get_aggregated_trace_log_spark_df_schema())

    print("Aggregated Trace DF:")
    all_aggregated_traces.show(truncate=False)
    all_aggregated_traces.printSchema()
    return all_aggregated_traces
