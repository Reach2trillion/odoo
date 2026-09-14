def post_init_hook(env):
    """Enable the shipping label auto-print on every existing Delivery
    operation type so the feature works right after installation."""
    PickingType = env['stock.picking.type']
    report_id = PickingType._default_shipping_label_report()
    if not report_id:
        return
    delivery_types = PickingType.with_context(active_test=False).search([('code', '=', 'outgoing')])
    delivery_types.write({
        'auto_print_shipping_label': True,
        'shipping_label_report_id': report_id,
    })
