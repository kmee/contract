# Copyright 2026 KMEE
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import Command

from .test_contract import TestContractBase, to_date


class TestContractInvoiceOffset(TestContractBase):
    """Invoice offset end to end: purchase contract, pre-paid, monthly,
    invoice issued 7 days before the start of each calendar month."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.contract.unlink()
        cls.contract2.unlink()

    def _create_contract(self, line_recurrence=False, **header_vals):
        vals = {
            "name": "Offset purchase contract",
            "partner_id": self.partner.id,
            "contract_type": "purchase",
            "line_recurrence": line_recurrence,
            "date_start": "2026-12-01",
            "recurring_rule_type": "monthly",
            "recurring_interval": 1,
            "recurring_invoicing_type": "pre-paid",
        }
        line_vals = {
            "product_id": self.product_1.id,
            "name": "Rent from #START# to #END#",
            "quantity": 1,
            "uom_id": self.product_1.uom_id.id,
            "price_unit": 100,
            # As in the other tests, a line created together with its contract
            # takes the field defaults, so the start date is given explicitly.
            "date_start": "2026-12-01",
        }
        if line_recurrence:
            # In line mode the recurrence lives on the lines
            for key in (
                "date_start",
                "recurring_rule_type",
                "recurring_interval",
                "recurring_invoicing_type",
                "recurring_invoicing_offset",
                "recurring_invoicing_offset_type",
            ):
                if key in vals:
                    line_vals[key] = vals.pop(key)
            line_vals.update(
                {
                    k: header_vals.pop(k)
                    for k in list(header_vals)
                    if k.startswith("recurring_invoicing_offset")
                }
            )
        vals.update(header_vals)
        vals["contract_line_ids"] = [Command.create(line_vals)]
        return self.env["contract.contract"].create(vals)

    def _invoices(self, contract):
        return contract._get_related_invoices().sorted("invoice_date")

    def _cron(self, date_ref):
        self.env["contract.contract"].cron_recurring_create_invoice(
            to_date(date_ref)
        )

    def _assert_two_cycles(self, contract):
        line = contract.contract_line_ids
        self.assertEqual(line.recurring_next_date, to_date("2026-11-24"))
        # Nothing is due before the offset date
        self._cron("2026-11-23")
        self.assertFalse(self._invoices(contract))
        # Cycle 1: invoiced on 24/11 for December
        self._cron("2026-11-24")
        invoices = self._invoices(contract)
        self.assertEqual(len(invoices), 1)
        self.assertEqual(invoices.invoice_date, to_date("2026-11-24"))
        self.assertEqual(line.last_date_invoiced, to_date("2026-12-31"))
        self.assertEqual(line.recurring_next_date, to_date("2026-12-25"))
        # Cycle 2: invoiced on 25/12 for January
        self._cron("2026-12-25")
        invoices = self._invoices(contract)
        self.assertEqual(len(invoices), 2)
        self.assertEqual(invoices[1].invoice_date, to_date("2026-12-25"))
        self.assertEqual(line.last_date_invoiced, to_date("2027-01-31"))
        self.assertEqual(line.recurring_next_date, to_date("2027-01-25"))

    def test_purchase_prepaid_offset_two_cycles_line_mode_off(self):
        """Offset on the header, header drives the lines."""
        contract = self._create_contract(
            recurring_invoicing_offset=-7,
            recurring_invoicing_offset_type="daily",
        )
        self._assert_two_cycles(contract)

    def test_header_only_offset_propagates_to_lines(self):
        contract = self._create_contract(
            recurring_invoicing_offset=-7,
            recurring_invoicing_offset_type="daily",
        )
        line = contract.contract_line_ids
        self.assertEqual(line.recurring_invoicing_offset, -7)
        self.assertEqual(line.recurring_invoicing_offset_type, "daily")
        self.assertEqual(contract.recurring_next_date, to_date("2026-11-24"))
        self.assertEqual(line.recurring_next_date, to_date("2026-11-24"))

    def test_header_offset_unit_propagates_to_lines(self):
        """Writing the header, as for the other recurrence fields, updates the
        lines (value, unit and the date of the next invoice)."""
        contract = self._create_contract()
        line = contract.contract_line_ids
        self.assertEqual(line.recurring_next_date, to_date("2026-12-01"))
        contract.write(
            {
                "recurring_invoicing_offset": -1,
                "recurring_invoicing_offset_type": "weekly",
            }
        )
        self.assertEqual(line.recurring_invoicing_offset, -1)
        self.assertEqual(line.recurring_invoicing_offset_type, "weekly")
        self.assertEqual(line.recurring_next_date, to_date("2026-11-24"))

    def test_line_recurrence_negative_offset_two_cycles(self):
        """With line_recurrence the constraint must accept an invoice date
        that precedes the end of the previous period."""
        contract = self._create_contract(
            line_recurrence=True,
            recurring_invoicing_offset=-7,
            recurring_invoicing_offset_type="daily",
        )
        self._assert_two_cycles(contract)

    def test_line_recurrence_header_offset_does_not_override_line(self):
        contract = self._create_contract(
            line_recurrence=True,
            recurring_invoicing_offset=-7,
            recurring_invoicing_offset_type="daily",
        )
        contract.recurring_invoicing_offset = -3
        self.assertEqual(contract.contract_line_ids.recurring_invoicing_offset, -7)

    def test_late_cron(self):
        """A cron that runs late invoices the right period once."""
        contract = self._create_contract(
            recurring_invoicing_offset=-7,
            recurring_invoicing_offset_type="daily",
        )
        line = contract.contract_line_ids
        self._cron("2026-12-03")
        invoices = self._invoices(contract)
        self.assertEqual(len(invoices), 1)
        self.assertEqual(line.last_date_invoiced, to_date("2026-12-31"))
        self.assertEqual(line.recurring_next_date, to_date("2026-12-25"))
        # The same late run does not catch up the following period
        self._cron("2026-12-03")
        self.assertEqual(len(self._invoices(contract)), 1)

    def test_duplicate_run(self):
        contract = self._create_contract(
            recurring_invoicing_offset=-7,
            recurring_invoicing_offset_type="daily",
        )
        self._cron("2026-11-24")
        self._cron("2026-11-24")
        self.assertEqual(len(self._invoices(contract)), 1)

    def test_duplicate_run_line_mode(self):
        contract = self._create_contract(
            line_recurrence=True,
            recurring_invoicing_offset=-7,
            recurring_invoicing_offset_type="daily",
        )
        self._cron("2026-11-24")
        self._cron("2026-11-24")
        self.assertEqual(len(self._invoices(contract)), 1)

    def test_offset_change_mid_life(self):
        contract = self._create_contract(
            recurring_invoicing_offset=-7,
            recurring_invoicing_offset_type="daily",
        )
        line = contract.contract_line_ids
        self._cron("2026-11-24")
        self.assertEqual(line.recurring_next_date, to_date("2026-12-25"))
        # Shift the offset on the header: the lines follow
        contract.recurring_invoicing_offset = -10
        self.assertEqual(line.recurring_invoicing_offset, -10)
        self.assertEqual(line.recurring_next_date, to_date("2026-12-22"))
        self.assertEqual(line.last_date_invoiced, to_date("2026-12-31"))
        # Not due yet on the old date's eve, due on the new one, no duplicates
        self._cron("2026-12-21")
        self.assertEqual(len(self._invoices(contract)), 1)
        self._cron("2026-12-22")
        invoices = self._invoices(contract)
        self.assertEqual(len(invoices), 2)
        self.assertEqual(invoices[1].invoice_date, to_date("2026-12-22"))
        self.assertEqual(line.last_date_invoiced, to_date("2027-01-31"))
        # Back to no offset: next invoice on the first day of the period
        contract.recurring_invoicing_offset = 0
        self.assertEqual(line.recurring_next_date, to_date("2027-02-01"))

    def test_offset_change_mid_life_line_mode(self):
        contract = self._create_contract(
            line_recurrence=True,
            recurring_invoicing_offset=-7,
            recurring_invoicing_offset_type="daily",
        )
        line = contract.contract_line_ids
        self._cron("2026-11-24")
        line.recurring_invoicing_offset = -10
        self.assertEqual(line.recurring_next_date, to_date("2026-12-22"))
        self._cron("2026-12-22")
        self.assertEqual(len(self._invoices(contract)), 2)

    def test_get_next_invoice_date_legacy_positional_signature(self):
        """Callers written before the offset unit existed keep working."""
        clm = self.env["contract.line"]
        self.assertEqual(
            clm.get_next_invoice_date(
                to_date("2026-12-01"), "pre-paid", -7, "monthly", 1, False
            ),
            to_date("2026-11-24"),
        )
        self.assertEqual(
            clm.get_next_invoice_date(
                to_date("2026-12-01"),
                "pre-paid",
                -1,
                "monthly",
                1,
                False,
                recurring_invoicing_offset_type="monthly",
            ),
            to_date("2026-11-01"),
        )
