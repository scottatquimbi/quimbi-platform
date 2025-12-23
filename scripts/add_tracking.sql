-- Add realistic tracking data to tickets

-- T-002: Thread color recommendation (delivered)
UPDATE support_app.tickets
SET custom_fields = '{
  "order_number": "L-10156",
  "order_date": "2025-11-20",
  "tracking_number": "1Z999AA10123456784",
  "tracking_url": "https://www.ups.com/track?tracknum=1Z999AA10123456784",
  "carrier": "UPS",
  "carrier_status": "Delivered",
  "last_update": "2025-11-23",
  "delivered_date": "2025-11-23",
  "items": [{"name": "Aurifil 50wt Thread Set", "quantity": 1, "sku": "AUR-50-SET"}]
}'::jsonb
WHERE ticket_number = 'T-002';

-- T-011: Damaged fabric (delivered, replacement shipped)
UPDATE support_app.tickets
SET custom_fields = '{
  "order_number": "L-10234",
  "order_date": "2025-11-25",
  "tracking_number": "9400111899562634567893",
  "tracking_url": "https://tools.usps.com/go/TrackConfirmAction?tLabels=9400111899562634567893",
  "carrier": "USPS",
  "carrier_status": "Delivered",
  "last_update": "2025-11-29",
  "delivered_date": "2025-11-29",
  "replacement_order": "L-10299",
  "replacement_tracking": "9400111899562634567894",
  "replacement_status": "Shipped",
  "items": [{"name": "Riley Blake Confetti Cottons", "quantity": 3, "sku": "RB-CC-001"}]
}'::jsonb
WHERE ticket_number = 'T-011';

-- T-014: Wrong item received
UPDATE support_app.tickets
SET custom_fields = '{
  "order_number": "L-10256",
  "order_date": "2025-11-26",
  "tracking_number": "1Z999AA10123456786",
  "tracking_url": "https://www.ups.com/track?tracknum=1Z999AA10123456786",
  "carrier": "UPS",
  "carrier_status": "Delivered",
  "last_update": "2025-11-30",
  "delivered_date": "2025-11-30",
  "return_label_created": "2025-12-01",
  "replacement_order": "L-10301",
  "replacement_tracking": "9400111899562634567895",
  "replacement_status": "Label Created",
  "items": [
    {"name": "Aurifil 40wt Thread Set (incorrect)", "quantity": 1, "sku": "AUR-40-SET"},
    {"name": "Aurifil 50wt Thread Set (correct, replacement)", "quantity": 1, "sku": "AUR-50-SET"}
  ]
}'::jsonb
WHERE ticket_number = 'T-014';

-- T-013: Pre-order inquiry
UPDATE support_app.tickets
SET custom_fields = '{
  "order_number": "L-10267",
  "order_date": "2025-11-26",
  "tracking_number": null,
  "carrier": null,
  "carrier_status": "Pre-Order - Awaiting Stock",
  "estimated_ship_date": "2025-12-15",
  "estimated_delivery": "2025-12-20",
  "items": [{"name": "Kaffe Fassett Collective 2024 Preview", "quantity": 1, "sku": "KF-2024-PRE"}]
}'::jsonb
WHERE ticket_number = 'T-013';

-- Verify updates
SELECT
  ticket_number,
  subject,
  custom_fields->>'order_number' as order_num,
  custom_fields->>'tracking_number' as tracking,
  custom_fields->>'carrier_status' as status
FROM support_app.tickets
WHERE ticket_number IN ('T-001', 'T-002', 'T-007', 'T-011', 'T-013', 'T-014')
ORDER BY ticket_number;
