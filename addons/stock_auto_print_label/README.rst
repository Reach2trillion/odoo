Auto Print Shipping Label (80x100 mm) on Delivery Validation
=============================================================

Odoo 18 module. When a **Delivery Order** is validated (the *Validate* button in
Inventory, or the Barcode app), the shipping label is printed automatically.

It plugs into Odoo's native *Print on Validation* mechanism (the same one used by
"Auto Print Delivery Slip"), so it works from the Inventory form view, the list
view (multi-validate) and the Barcode app.

Configuration
-------------

Inventory > Configuration > Operation Types > *Delivery Orders* > **Hardware** tab >
*Print on Validation*:

* **Shipping Label**: tick to print the label at validation. It is ticked
  automatically on all delivery operation types when the module is installed.
* **Label**: which PDF report is used. Any PDF report on Transfers can be chosen.
  Defaults to the *Shipping Label* report of the ``stock_shipping_label`` module
  when that module is installed, otherwise to the 80x100 mm label bundled here.
* **Print via**:

  * ``Browser print dialog`` (default): the PDF is generated and the browser's
    print dialog opens on it right away.
  * ``Standard Odoo``: the label follows Odoo's normal report flow, i.e. a PDF
    download, or a direct print when an IoT Box / PrintNode printer is routed to
    the report.

Getting a fully silent print
----------------------------

A browser cannot print without asking unless you tell it to:

* **Chrome / Edge**: start the browser with ``--kiosk-printing`` and set the
  label printer as the default printer (with the 80x100 mm paper size). The
  print dialog is then auto-accepted.
* **Odoo IoT Box (Enterprise)** or **PrintNode**: set *Print via* to
  ``Standard Odoo`` and route the label report to the printer in the IoT /
  PrintNode configuration.

Bundled label
-------------

*Shipping Label 80x100 (Auto Print)*: 80 x 100 mm portrait, 3 mm margins. Shows
company, transfer reference and date, *Deliver To* name / phone / address, order
reference, carrier and tracking reference (when the Delivery module is
installed), item count and weight, order total (when linked to a sales order),
up to 6 product lines, and a Code128 barcode of the transfer reference.

Installation
------------

Copy ``stock_auto_print_label`` into an addons path, update the apps list and
install *Auto Print Shipping Label (80x100 mm) on Delivery Validation*.
