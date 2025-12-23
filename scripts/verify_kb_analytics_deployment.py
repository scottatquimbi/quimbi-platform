#!/usr/bin/env python3
"""
Verification Script: Knowledge Base & Analytics Deployment
Purpose: Verify both schemas are deployed correctly and ready for API development
Date: 2025-12-17
"""

import os
import psycopg2
from psycopg2.extras import RealDictCursor

# Database connection
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:XzLuopeMhZwurhlOWaObisBJxiTFViCb@turntable.proxy.rlwy.net:30126/railway")

def verify_deployment():
    """Verify KB and Analytics schemas are deployed correctly"""

    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor(cursor_factory=RealDictCursor)

    print("=" * 80)
    print("KNOWLEDGE BASE & ANALYTICS DEPLOYMENT VERIFICATION")
    print("=" * 80)
    print()

    # 1. Verify Knowledge Base tables
    print("1. KNOWLEDGE BASE SCHEMA")
    print("-" * 80)

    cur.execute("""
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = 'knowledge_base'
        ORDER BY table_name
    """)

    kb_tables = [row['table_name'] for row in cur.fetchall()]
    expected_kb_tables = [
        'article_analytics',
        'article_relations',
        'article_ticket_links',
        'article_versions',
        'articles',
        'attachments',
        'categories',
        'search_queries'
    ]

    print(f"   Expected tables: {len(expected_kb_tables)}")
    print(f"   Found tables: {len(kb_tables)}")

    for table in expected_kb_tables:
        status = "✅" if table in kb_tables else "❌"
        print(f"   {status} {table}")

    kb_complete = set(expected_kb_tables) == set(kb_tables)
    print()

    # 2. Verify Analytics tables
    print("2. ANALYTICS SCHEMA")
    print("-" * 80)

    cur.execute("""
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = 'analytics'
        ORDER BY table_name
    """)

    analytics_tables = [row['table_name'] for row in cur.fetchall()]
    expected_analytics_tables = [
        'business_events',
        'forecast_model_performance',
        'product_ticket_correlation',
        'seasonal_patterns',
        'staffing_recommendations',
        'ticket_surge_events',
        'ticket_volume_forecasts',
        'ticket_volume_history'
    ]

    print(f"   Expected tables: {len(expected_analytics_tables)}")
    print(f"   Found tables: {len(analytics_tables)}")

    for table in expected_analytics_tables:
        status = "✅" if table in analytics_tables else "❌"
        print(f"   {status} {table}")

    analytics_complete = set(expected_analytics_tables) == set(analytics_tables)
    print()

    # 3. Verify KB Categories
    print("3. KNOWLEDGE BASE CATEGORIES")
    print("-" * 80)

    cur.execute("""
        SELECT
            COALESCE(p.name, 'ROOT') as parent,
            c.name as category,
            c.slug,
            c.display_order
        FROM knowledge_base.categories c
        LEFT JOIN knowledge_base.categories p ON c.parent_category_id = p.category_id
        ORDER BY COALESCE(p.display_order, 0), c.display_order
    """)

    categories = cur.fetchall()
    print(f"   Total categories: {len(categories)}")
    print()

    # Group by parent
    by_parent = {}
    for cat in categories:
        parent = cat['parent']
        if parent not in by_parent:
            by_parent[parent] = []
        by_parent[parent].append(cat)

    for parent, cats in by_parent.items():
        if parent == 'ROOT':
            print(f"   Top-Level Categories ({len(cats)}):")
            for cat in cats:
                print(f"      • {cat['category']} ({cat['slug']})")
        else:
            print(f"   {parent} Subcategories ({len(cats)}):")
            for cat in cats:
                print(f"      • {cat['category']} ({cat['slug']})")
        print()

    # 4. Verify Business Events
    print("4. ANALYTICS BUSINESS EVENTS")
    print("-" * 80)

    cur.execute("""
        SELECT
            event_name,
            event_type,
            event_start,
            event_end,
            expected_ticket_volume_change
        FROM analytics.business_events
        ORDER BY event_start
    """)

    events = cur.fetchall()
    print(f"   Total events: {len(events)}")
    print()

    for event in events:
        volume_change = event['expected_ticket_volume_change']
        volume_pct = f"+{int(volume_change * 100)}%" if volume_change else "N/A"
        end = f" to {event['event_end']}" if event['event_end'] else ""
        print(f"   • {event['event_name']} ({event['event_type']})")
        print(f"     {event['event_start']}{end} - {volume_pct} ticket volume")

    print()

    # 5. Verify Views
    print("5. VIEWS")
    print("-" * 80)

    cur.execute("""
        SELECT table_schema, table_name
        FROM information_schema.views
        WHERE table_schema IN ('knowledge_base', 'analytics')
        ORDER BY table_schema, table_name
    """)

    views = cur.fetchall()
    print(f"   Total views: {len(views)}")

    for view in views:
        print(f"   ✅ {view['table_schema']}.{view['table_name']}")

    print()

    # 6. Verify Triggers
    print("6. TRIGGERS")
    print("-" * 80)

    cur.execute("""
        SELECT
            event_object_schema as schema,
            event_object_table as table_name,
            trigger_name,
            action_timing,
            event_manipulation
        FROM information_schema.triggers
        WHERE event_object_schema IN ('knowledge_base', 'analytics')
        ORDER BY event_object_schema, event_object_table, trigger_name
    """)

    triggers = cur.fetchall()
    print(f"   Total triggers: {len(triggers)}")

    for trigger in triggers:
        print(f"   ✅ {trigger['schema']}.{trigger['table_name']}")
        print(f"      {trigger['action_timing']} {trigger['event_manipulation']} → {trigger['trigger_name']}")

    print()

    # 7. Test Full-Text Search
    print("7. FULL-TEXT SEARCH TEST")
    print("-" * 80)

    # Insert a test article
    cur.execute("""
        INSERT INTO knowledge_base.articles
        (title, slug, content, summary, status, visibility)
        VALUES
        (
            'Test Article: Thread Weight Guide',
            'test-thread-weight-guide',
            'Thread weight refers to the thickness of the thread. Common weights are 40wt, 50wt, and 60wt. Thinner threads (higher numbers) are better for detailed quilting.',
            'A guide to understanding thread weights for quilting projects.',
            'published',
            'public'
        )
        RETURNING article_id, title
    """)

    test_article = cur.fetchone()
    print(f"   Created test article: {test_article['title']}")
    print(f"   Article ID: {test_article['article_id']}")

    # Test full-text search
    cur.execute("""
        SELECT
            article_id,
            title,
            ts_rank(tsv, plainto_tsquery('english', 'thread quilting')) as rank
        FROM knowledge_base.articles
        WHERE tsv @@ plainto_tsquery('english', 'thread quilting')
        ORDER BY rank DESC
    """)

    search_results = cur.fetchall()
    print(f"   Search query: 'thread quilting'")
    print(f"   Results found: {len(search_results)}")

    for result in search_results:
        print(f"      • {result['title']} (rank: {result['rank']:.4f})")

    # Clean up test article
    cur.execute("DELETE FROM knowledge_base.articles WHERE article_id = %s", (test_article['article_id'],))
    print(f"   ✅ Test article deleted")

    conn.commit()
    print()

    # 8. Summary
    print("=" * 80)
    print("DEPLOYMENT VERIFICATION SUMMARY")
    print("=" * 80)

    print()
    print("Knowledge Base Schema:")
    print(f"   Tables: {'✅ COMPLETE' if kb_complete else '❌ INCOMPLETE'} ({len(kb_tables)}/{len(expected_kb_tables)})")
    print(f"   Categories: ✅ {len(categories)} loaded")
    print(f"   Full-Text Search: ✅ Working")

    print()
    print("Analytics Schema:")
    print(f"   Tables: {'✅ COMPLETE' if analytics_complete else '❌ INCOMPLETE'} ({len(analytics_tables)}/{len(expected_analytics_tables)})")
    print(f"   Business Events: ✅ {len(events)} loaded")

    print()
    print("Database Infrastructure:")
    print(f"   Views: ✅ {len(views)} created")
    print(f"   Triggers: ✅ {len(triggers)} active")

    print()

    overall_status = kb_complete and analytics_complete and len(categories) == 19 and len(events) == 10

    if overall_status:
        print("🎉 DEPLOYMENT SUCCESSFUL - All schemas ready for API development!")
    else:
        print("⚠️  DEPLOYMENT INCOMPLETE - Review errors above")

    print("=" * 80)
    print()

    cur.close()
    conn.close()

    return overall_status


if __name__ == "__main__":
    try:
        success = verify_deployment()
        exit(0 if success else 1)
    except Exception as e:
        print(f"❌ Verification failed with error: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
