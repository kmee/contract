# Copyright 2024 KMEE
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import _, api, fields, models


class ProjectTask(models.Model):

    _inherit = "project.task"

    contract_line_id = fields.Many2one(
        "contract.line",
        "Contract Item",
        copy=False,
        # index="btree_not_null",
        domain=(
            "[('partner_id', '=?', partner_id), "
            "'|', ('company_id', '=', False), ('company_id', '=', company_id)]"
        ),
        help=(
            "Recurring invoicing contract item that will be used to "
            "determine the timesheet invoicing type."
        ),
    )
    contract_id = fields.Many2one(
        related="contract_line_id.contract_id",
        readonly=True,
        help="Recurring invoicing contract",
    )
