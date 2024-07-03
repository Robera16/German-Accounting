import frappe
from frappe.utils import cint, flt
from frappe import _, msgprint
import json
from frappe.query_builder import DocType


def get_users_with_role(role: str) -> list[str]:
	User = DocType("User")
	HasRole = DocType("Has Role")

	return (
		frappe.qb.from_(HasRole)
		.from_(User)
		.where(
			(HasRole.role == role)
			& (User.enabled == 1)
			& (HasRole.parent == User.name)
		)
		.select(User.email)
		.distinct()
		.run(pluck=True)
	)

@frappe.whitelist()
def send_emails(users, docname):
	try:
		users = json.loads(users)
		subject = _("Anfrage zur Belegfreigabe für {0}.").format(docname)
		message = _("Bitte geben Sie den Beleg {0} frei.").format( frappe.utils.get_url_to_form("Sales Order", docname))
		
		frappe.sendmail(
			recipients= users, 
			subject=subject, 
			message=message,
			delayed=False,
			retry=3 
		)
		return {"status": "success", "message": _("Emails sent successfully.")}
	except Exception as e:
		return {"status": "error", "message": str(e)}

def user_has_imat_belegfreigabe_role():
	user = frappe.session.user
	role  = "German Accounting Belegfreigabe"
	
	return frappe.db.exists("Has Role", {
        "parent": user,
        "role": role,
        "parenttype": "User", 
    })


@frappe.whitelist()
def get_credit_limit(customer, company):
	credit_limit = None

	if customer:
		credit_limit = frappe.db.get_value(
			"Customer Credit Limit",
			{"parent": customer, "parenttype": "Customer", "company": company},
			"credit_limit",
		)

		if not credit_limit:
			customer_group = frappe.get_cached_value("Customer", customer, "customer_group")

			result = frappe.db.get_values(
				"Customer Credit Limit",
				{"parent": customer_group, "parenttype": "Customer Group", "company": company},
				fieldname=["credit_limit", "bypass_credit_limit_check"],
				as_dict=True,
			)
			if result and not result[0].bypass_credit_limit_check:
				credit_limit = result[0].credit_limit

	if not credit_limit:
		credit_limit = frappe.get_cached_value("Company", company, "credit_limit")

	return flt(credit_limit) 


def get_customer_outstanding(customer, company, total):

	return flt(total)



def check_credit_limit_for_customer(docname, customer, company, total):
	# if bypass credit limit check is set to true (1) at sales_order level,
	# then we need not to check credit limit and vise versa
	if not cint(
        frappe.db.get_value(
                "Customer Credit Limit",
                {"parent": customer, "parenttype": "Customer", "company": company},
                "bypass_credit_limit_check",
        )
	):
		credit_limit = get_credit_limit(customer, company)
		if not credit_limit:
			return

		customer_outstanding =  get_customer_outstanding(customer, company, total)
		if credit_limit > 0 and flt(customer_outstanding) > credit_limit:

			message = _("Credit limit has been crossed for customer {0} which has total outstanding amount of {1} and credit limit of {2}").format(
                customer, customer_outstanding, credit_limit
            )
			return message

@frappe.whitelist()
def check_credit_limit(docname, customer, company, total, method=None):

  message = check_credit_limit_for_customer(docname, customer, company, total)

  if message is None:
    message = ""

  table = ""
  button_label = "Acknowledge"

  if not user_has_imat_belegfreigabe_role():
    button_label = "Request Approval"
    formatted_user_rows = ""
    users = get_users_with_role("German Accounting Belegfreigabe")

    for user in users:
      formatted_user_rows += f"""
      		<tr>
                <td style="padding: 5px;"><input type="checkbox" name="user_checkbox" value="{user}"></td>
                <td style="padding: 5px;">{user}</td>
            </tr>"""

    table= """
            <table>
                <thead>
                    <tr>
                        <th style="padding: 5px;"><input type="checkbox" id="select-all"></th>
                        <th style="padding: 5px;">{}</th>
                    </tr>
                </thead>
                <tbody>
                    {}
                </tbody>
            </table>
    """.format(_("Users"), formatted_user_rows)

  return {
	"message": message, 
	"users": table, 
	"button_label": button_label
  }

