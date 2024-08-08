# Copyright 2024 KMEE
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import _, api, fields, models


class ContractContract(models.Model):

    _inherit = "contract.contract"

    project_ids = fields.One2many(
        'project.project',
        'contract_id',
    )

    project_count = fields.Integer(compute="_compute_project_count")

    @api.depends("project_ids")
    def _compute_project_count(self):
        for rec in self:
            rec.project_count = len(rec.project_ids)

    def action_view_projects(self):
        self.ensure_one()
        projects = self.project_ids
        action = {
            "name": _("Projects"),
            "view_mode": "tree,form",
            "res_model": "project.project",
            "type": "ir.actions.act_window",
            "domain": [("id", "in", projects.ids)],
        }
        if len(projects) == 1:
            # If there is only one order, open it directly
            action.update({"view_mode": "form", "res_id": projects.id})
        return action
