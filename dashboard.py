#!/usr/bin/env python3
"""
Customer Segmentation Dashboard - Streamlit

Quick exploratory dashboard for behavioral segmentation analysis.

Run:
    streamlit run dashboard.py

Then open: http://localhost:8501
"""

import streamlit as st
import asyncio
import asyncpg
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
import os
import json

# Page config
st.set_page_config(
    page_title="Customer Segmentation Dashboard",
    page_icon="🎯",
    layout="wide"
)

# Database connection
@st.cache_resource
def get_connection():
    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        st.error("❌ DATABASE_URL environment variable not set")
        st.stop()
    return database_url

# Async query helper
async def run_query(query, params=None):
    conn = await asyncpg.connect(get_connection())
    try:
        if params:
            result = await conn.fetch(query, *params)
        else:
            result = await conn.fetch(query)
        return [dict(row) for row in result]
    finally:
        await conn.close()

def query(sql, params=None):
    """Synchronous wrapper for async queries"""
    return asyncio.run(run_query(sql, params))

# Header
st.title("🎯 Customer Segmentation Dashboard")
st.markdown("Real-time behavioral segmentation analysis")
st.markdown("---")

# Sidebar filters
with st.sidebar:
    st.header("Filters")

    # Get available axes
    axes_query = """
        SELECT DISTINCT jsonb_object_keys(dominant_segments) as axis
        FROM customer_profiles
        WHERE dominant_segments <> '{}'
        ORDER BY axis
    """
    axes_data = query(axes_query)
    available_axes = [row['axis'] for row in axes_data]

    selected_axis = st.selectbox(
        "Focus Axis",
        options=['All'] + available_axes,
        index=0
    )

    st.markdown("---")
    st.markdown("### About")
    st.markdown("This dashboard shows behavioral segmentation across 16+ dimensions.")

# Health Status Section
st.header("🏥 System Health")
health_cols = st.columns(4)

# Coverage Rate
coverage_query = """
    SELECT
        COUNT(*) FILTER (WHERE segment_memberships <> '{}')::float / COUNT(*) * 100 as coverage_rate
    FROM customer_profiles
"""
coverage_rate = query(coverage_query)[0]['coverage_rate'] or 0

# Data Freshness
freshness_query = """
    SELECT
        EXTRACT(EPOCH FROM (NOW() - MAX(last_updated))) / 86400 as days_old
    FROM customer_profiles
    WHERE segment_memberships <> '{}'
"""
freshness_result = query(freshness_query)
days_old = freshness_result[0]['days_old'] if freshness_result[0]['days_old'] else 0

# Segment Balance (CV)
balance_query = """
    SELECT
        STDDEV(cnt)::float / NULLIF(AVG(cnt), 0) as cv
    FROM (
        SELECT COUNT(*) as cnt
        FROM customer_profiles
        WHERE dominant_segments <> '{}'
        GROUP BY jsonb_object_keys(dominant_segments)
    ) t
"""
balance_cv = query(balance_query)[0]['cv'] or 0

# High Churn Risk %
churn_query = """
    SELECT
        COUNT(*) FILTER (WHERE churn_risk_score > 0.7)::float / NULLIF(COUNT(*), 0) * 100 as high_risk_pct
    FROM customer_profiles
    WHERE churn_risk_score IS NOT NULL
"""
churn_result = query(churn_query)
high_risk_pct = churn_result[0]['high_risk_pct'] if churn_result else 0

with health_cols[0]:
    coverage_status = "✅" if coverage_rate > 95 else "⚠️" if coverage_rate > 90 else "❌"
    st.metric("Coverage Rate", f"{coverage_rate:.1f}%", delta=coverage_status)

with health_cols[1]:
    freshness_status = "✅" if days_old < 7 else "⚠️" if days_old < 30 else "❌"
    st.metric("Data Freshness", f"{days_old:.0f} days", delta=freshness_status)

with health_cols[2]:
    balance_status = "✅" if balance_cv < 0.5 else "⚠️" if balance_cv < 0.7 else "❌"
    st.metric("Balance Score", f"{balance_cv:.2f}", delta=balance_status)

with health_cols[3]:
    risk_status = "✅" if high_risk_pct < 20 else "⚠️" if high_risk_pct < 30 else "❌"
    st.metric("High Churn Risk", f"{high_risk_pct:.1f}%", delta=risk_status)

st.markdown("---")

# Business KPIs
st.header("💼 Business KPIs")

col1, col2, col3, col4 = st.columns(4)

# Total customers
total_query = "SELECT COUNT(*) as total FROM customer_profiles"
total_customers = query(total_query)[0]['total']

# Segmented customers
segmented_query = """
    SELECT COUNT(*) as segmented
    FROM customer_profiles
    WHERE dominant_segments <> '{}'
"""
segmented_customers = query(segmented_query)[0]['segmented']

# Total LTV
ltv_query = "SELECT SUM(lifetime_value) as total_ltv FROM customer_profiles"
total_ltv = query(ltv_query)[0]['total_ltv'] or 0

# Average AOV
aov_query = "SELECT AVG(avg_order_value) as avg_aov FROM customer_profiles WHERE avg_order_value IS NOT NULL"
avg_aov = query(aov_query)[0]['avg_aov'] or 0

with col1:
    st.metric("Total Customers", f"{total_customers:,}")

with col2:
    st.metric("Total LTV", f"${total_ltv:,.0f}")

with col3:
    st.metric("Average AOV", f"${avg_aov:.2f}")

with col4:
    # Repeat purchase rate
    repeat_query = """
        SELECT
            COUNT(*) FILTER (WHERE total_orders > 1)::float / NULLIF(COUNT(*), 0) * 100 as repeat_rate
        FROM customer_profiles
        WHERE total_orders IS NOT NULL
    """
    repeat_rate = query(repeat_query)[0]['repeat_rate'] or 0
    st.metric("Repeat Rate", f"{repeat_rate:.1f}%")

st.markdown("---")

# Main content
if selected_axis == 'All':
    # Overview - All axes
    st.header("📊 Segment Distribution Across All Axes")

    # Get distribution
    distribution_query = """
        SELECT
            jsonb_object_keys(dominant_segments) as axis,
            COUNT(*) as customer_count
        FROM customer_profiles
        WHERE dominant_segments <> '{}'
        GROUP BY axis
        ORDER BY customer_count DESC
    """
    dist_data = query(distribution_query)
    df_dist = pd.DataFrame(dist_data)

    col1, col2 = st.columns(2)

    with col1:
        # Bar chart
        fig = px.bar(
            df_dist,
            x='axis',
            y='customer_count',
            title='Customer Coverage by Axis',
            labels={'axis': 'Behavioral Axis', 'customer_count': 'Customers'}
        )
        fig.update_layout(xaxis_tickangle=-45)
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        # Pie chart
        fig = px.pie(
            df_dist,
            values='customer_count',
            names='axis',
            title='Relative Coverage by Axis'
        )
        st.plotly_chart(fig, use_container_width=True)

    # Top segments table
    st.subheader("🏆 Top Segments Across All Axes")

    top_segments_query = """
        SELECT
            jsonb_object_keys(dominant_segments) as axis,
            dominant_segments->>jsonb_object_keys(dominant_segments) as segment,
            COUNT(*) as customers,
            AVG(lifetime_value) as avg_ltv,
            SUM(lifetime_value) as total_ltv
        FROM customer_profiles
        WHERE dominant_segments <> '{}'
        GROUP BY axis, segment
        ORDER BY customers DESC
        LIMIT 20
    """
    top_data = query(top_segments_query)
    df_top = pd.DataFrame(top_data)
    df_top['avg_ltv'] = df_top['avg_ltv'].apply(lambda x: f"${x:,.2f}")
    df_top['total_ltv'] = df_top['total_ltv'].apply(lambda x: f"${x:,.0f}")

    st.dataframe(df_top, use_container_width=True, hide_index=True)

else:
    # Specific axis deep dive
    st.header(f"📊 Deep Dive: {selected_axis.replace('_', ' ').title()}")

    # Segment distribution for this axis
    axis_dist_query = """
        SELECT
            dominant_segments->>$1 as segment,
            COUNT(*) as customers,
            AVG(lifetime_value) as avg_ltv,
            AVG(total_orders) as avg_orders,
            AVG(avg_order_value) as avg_aov,
            SUM(lifetime_value) as total_ltv
        FROM customer_profiles
        WHERE dominant_segments ? $1
        GROUP BY segment
        ORDER BY customers DESC
    """
    axis_data = query(axis_dist_query, [selected_axis])
    df_axis = pd.DataFrame(axis_data)

    if len(df_axis) > 0:
        col1, col2 = st.columns(2)

        with col1:
            # Segment size
            fig = px.bar(
                df_axis,
                x='segment',
                y='customers',
                title=f'Customer Count by {selected_axis.replace("_", " ").title()} Segment',
                labels={'segment': 'Segment', 'customers': 'Customer Count'}
            )
            st.plotly_chart(fig, use_container_width=True)

        with col2:
            # LTV distribution
            fig = px.bar(
                df_axis,
                x='segment',
                y='avg_ltv',
                title=f'Average LTV by {selected_axis.replace("_", " ").title()} Segment',
                labels={'segment': 'Segment', 'avg_ltv': 'Avg LTV ($)'}
            )
            st.plotly_chart(fig, use_container_width=True)

        # Detailed table
        st.subheader("📋 Segment Details")
        df_display = df_axis.copy()
        df_display['avg_ltv'] = df_display['avg_ltv'].apply(lambda x: f"${x:,.2f}")
        df_display['avg_aov'] = df_display['avg_aov'].apply(lambda x: f"${x:,.2f}")
        df_display['total_ltv'] = df_display['total_ltv'].apply(lambda x: f"${x:,.0f}")
        df_display['avg_orders'] = df_display['avg_orders'].apply(lambda x: f"{x:.1f}")

        st.dataframe(df_display, use_container_width=True, hide_index=True)

        # Scatter: Orders vs LTV
        st.subheader("📈 Orders vs LTV by Segment")
        fig = px.scatter(
            df_axis,
            x='avg_orders',
            y='avg_ltv',
            size='customers',
            color='segment',
            title=f'{selected_axis.replace("_", " ").title()}: Orders vs Lifetime Value',
            labels={
                'avg_orders': 'Average Orders',
                'avg_ltv': 'Average Lifetime Value ($)',
                'customers': 'Customer Count'
            }
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.warning(f"No data found for axis: {selected_axis}")

# Footer
st.markdown("---")
st.markdown("### 🔄 Segment Cross-Analysis")

# Cross-axis analysis
col1, col2 = st.columns(2)

with col1:
    axis1 = st.selectbox("Axis 1", available_axes, index=0, key='axis1')

with col2:
    axis2 = st.selectbox("Axis 2", available_axes, index=1 if len(available_axes) > 1 else 0, key='axis2')

if axis1 and axis2 and axis1 != axis2:
    cross_query = """
        SELECT
            dominant_segments->>$1 as segment1,
            dominant_segments->>$2 as segment2,
            COUNT(*) as customers,
            AVG(lifetime_value) as avg_ltv
        FROM customer_profiles
        WHERE dominant_segments ? $1 AND dominant_segments ? $2
        GROUP BY segment1, segment2
        ORDER BY customers DESC
        LIMIT 20
    """
    cross_data = query(cross_query, [axis1, axis2])
    df_cross = pd.DataFrame(cross_data)

    if len(df_cross) > 0:
        # Heatmap
        pivot = df_cross.pivot(index='segment1', columns='segment2', values='customers').fillna(0)

        fig = go.Figure(data=go.Heatmap(
            z=pivot.values,
            x=pivot.columns,
            y=pivot.index,
            colorscale='Blues',
            text=pivot.values,
            texttemplate='%{text:.0f}',
            textfont={"size": 10}
        ))

        fig.update_layout(
            title=f'Customer Distribution: {axis1.replace("_", " ").title()} vs {axis2.replace("_", " ").title()}',
            xaxis_title=axis2.replace("_", " ").title(),
            yaxis_title=axis1.replace("_", " ").title()
        )

        st.plotly_chart(fig, use_container_width=True)
    else:
        st.warning("No cross-axis data available for selected combination")

# Refresh button
st.markdown("---")
if st.button("🔄 Refresh Dashboard"):
    st.cache_resource.clear()
    st.rerun()

st.caption(f"Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
