from datetime import date, datetime, timedelta
import csv
import json
import os

LOW_STOCK_LIMIT = 10
TABLE_HEADER = f"{'ID':<5}{'Name':<22}{'Type':<14}{'Price':<12}{'Qty':<8}{'Expiry'}"


# ============================================================
#  CUSTOM EXCEPTIONS
# ============================================================
class PharmacyError(Exception):
    """Base class for all pharmacy errors."""


class MedicineNotFoundError(PharmacyError):
    """Raised when a medicine ID does not exist."""


class InsufficientStockError(PharmacyError):
    """Raised when requested quantity is more than what is available."""


class ExpiredMedicineError(PharmacyError):
    """Raised when someone tries to sell an expired medicine."""


class PrescriptionRequiredError(PharmacyError):
    """Raised when a prescription medicine is sold without a prescription."""


# ============================================================
#  MODEL CLASSES
# ============================================================
class Medicine:
    """A general (over-the-counter) medicine."""

    requires_prescription = False

    def __init__(self, medicine_id, name, price, quantity, expiry_date):
        self._medicine_id = medicine_id
        self._name = name
        self._price = price
        self._quantity = quantity
        self._expiry_date = expiry_date

    # ---- read-only properties (encapsulation) ----
    @property
    def medicine_id(self):
        return self._medicine_id

    @property
    def name(self):
        return self._name

    @property
    def price(self):
        return self._price

    @property
    def quantity(self):
        return self._quantity

    @property
    def expiry_date(self):
        return self._expiry_date

    @property
    def category(self):
        return "General"

    # ---- behaviour ----
    def update_price(self, new_price):
        if new_price <= 0:
            raise ValueError("Price must be greater than zero.")
        self._price = new_price

    def add_stock(self, amount):
        self._quantity += amount

    def remove_stock(self, amount):
        if amount > self._quantity:
            raise InsufficientStockError(
                f"Only {self._quantity} units of '{self._name}' available.")
        self._quantity -= amount

    def is_expired(self, today=None):
        today = today or date.today()
        return self._expiry_date < today

    def days_to_expiry(self, today=None):
        today = today or date.today()
        return (self._expiry_date - today).days

    def is_low_stock(self, limit=LOW_STOCK_LIMIT):
        return self._quantity <= limit

    def __str__(self):
        price_text = "Rs." + format(self._price, ".2f")
        return (f"{self._medicine_id:<5}{self._name[:21]:<22}"
                f"{self.category:<14}{price_text:<12}"
                f"{self._quantity:<8}{self._expiry_date}")


class PrescriptionMedicine(Medicine):
    """A medicine that can only be sold with a valid prescription (inheritance)."""

    requires_prescription = True

    @property
    def category(self):
        return "Prescription"


class Customer:
    def __init__(self, name, phone):
        self.name = name
        self.phone = phone


class Sale:
    """One bill generated for a customer."""

    def __init__(self, bill_no, customer, items):
        # items: list of (medicine_name, quantity, unit_price)
        self.bill_no = bill_no
        self.customer = customer
        self.items = items
        self.timestamp = datetime.now()

    @property
    def total(self):
        return sum(qty * price for _, qty, price in self.items)

    def receipt(self):
        line = "-" * 52
        lines = [
            line,
            "                    PHARMACY BILL",
            line,
            f"Bill No  : {self.bill_no}",
            f"Customer : {self.customer.name}",
            f"Phone    : {self.customer.phone or 'N/A'}",
            f"Date     : {self.timestamp:%d-%m-%Y %H:%M}",
            line,
            f"{'Item':<24}{'Qty':>5}{'Price':>10}{'Amount':>13}",
            line,
        ]
        for name, qty, price in self.items:
            lines.append(f"{name[:23]:<24}{qty:>5}{price:>10.2f}{qty * price:>13.2f}")
        lines += [line, f"{'TOTAL':<39}Rs.{self.total:>9.2f}", line]
        return "\n".join(lines)


# ============================================================
#  BUSINESS LOGIC CLASS
# ============================================================
class Pharmacy:
    """Manages medicines, sales and reports. Holds all data in memory."""

    def __init__(self, name):
        self.name = name
        self._medicines = {}          # medicine_id -> Medicine
        self._sales = []              # list of Sale
        self._next_medicine_id = 1
        self._next_bill_no = 1001

    # ---- medicine management ----
    def add_medicine(self, name, price, quantity, expiry_date, prescription=False):
        cls = PrescriptionMedicine if prescription else Medicine
        medicine = cls(self._next_medicine_id, name, price, quantity, expiry_date)
        self._medicines[medicine.medicine_id] = medicine
        self._next_medicine_id += 1
        return medicine

    def get_medicine(self, medicine_id):
        try:
            return self._medicines[medicine_id]
        except KeyError:
            raise MedicineNotFoundError(f"No medicine found with ID {medicine_id}.")

    def all_medicines(self):
        return list(self._medicines.values())

    def search(self, keyword):
        keyword = keyword.lower()
        return [m for m in self._medicines.values() if keyword in m.name.lower()]

    def restock(self, medicine_id, amount):
        self.get_medicine(medicine_id).add_stock(amount)

    def delete_medicine(self, medicine_id):
        self.get_medicine(medicine_id)             # raises if not found
        del self._medicines[medicine_id]

    # ---- alerts ----
    def low_stock_items(self):
        return [m for m in self._medicines.values() if m.is_low_stock()]

    def expired_items(self):
        return [m for m in self._medicines.values() if m.is_expired()]

    def expiring_soon(self, days=30):
        return [m for m in self._medicines.values()
                if not m.is_expired() and m.days_to_expiry() <= days]

    # ---- sales ----
    def create_sale(self, customer, cart, prescription_given=False):
        """cart is a list of (medicine_id, quantity) tuples."""
        if not cart:
            raise PharmacyError("Cart is empty.")

        # 1. Combine duplicate entries of the same medicine
        requested = {}
        for medicine_id, qty in cart:
            requested[medicine_id] = requested.get(medicine_id, 0) + qty

        # 2. Validate EVERYTHING before touching any stock
        for medicine_id, qty in requested.items():
            medicine = self.get_medicine(medicine_id)
            if medicine.is_expired():
                raise ExpiredMedicineError(f"'{medicine.name}' has expired and cannot be sold.")
            if medicine.requires_prescription and not prescription_given:
                raise PrescriptionRequiredError(
                    f"'{medicine.name}' requires a valid prescription.")
            if qty > medicine.quantity:
                raise InsufficientStockError(
                    f"Only {medicine.quantity} units of '{medicine.name}' available.")

        # 3. All checks passed - reduce stock and create the bill
        items = []
        for medicine_id, qty in requested.items():
            medicine = self.get_medicine(medicine_id)
            medicine.remove_stock(qty)
            items.append((medicine.name, qty, medicine.price))

        sale = Sale(self._next_bill_no, customer, items)
        self._next_bill_no += 1
        self._sales.append(sale)
        return sale

    def sales_history(self):
        return list(self._sales)

    def total_revenue(self):
        return sum(sale.total for sale in self._sales)

    # ---- CSV Import / Export ----
    def export_to_csv(self, med_file="medicines.csv", sales_file="sales.csv"):
        with open(med_file, mode="w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["medicine_id", "name", "price", "quantity", "expiry_date", "prescription"])
            for m in self._medicines.values():
                writer.writerow([
                    m.medicine_id,
                    m.name,
                    m.price,
                    m.quantity,
                    m.expiry_date.strftime("%Y-%m-%d"),
                    m.requires_prescription
                ])

        with open(sales_file, mode="w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["bill_no", "customer_name", "customer_phone", "timestamp", "items_json"])
            for s in self._sales:
                writer.writerow([
                    s.bill_no,
                    s.customer.name,
                    s.customer.phone,
                    s.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                    json.dumps(s.items)
                ])

    def import_from_csv(self, med_file="medicines.csv", sales_file="sales.csv"):
        if os.path.exists(med_file):
            with open(med_file, mode="r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                self._medicines.clear()
                max_id = 0
                for row in reader:
                    med_id = int(row["medicine_id"])
                    name = row["name"]
                    price = float(row["price"])
                    qty = int(row["quantity"])
                    expiry = datetime.strptime(row["expiry_date"], "%Y-%m-%d").date()
                    prescription = str(row["prescription"]).lower() in ("true", "1", "yes")

                    cls = PrescriptionMedicine if prescription else Medicine
                    medicine = cls(med_id, name, price, qty, expiry)
                    self._medicines[med_id] = medicine
                    if med_id > max_id:
                        max_id = med_id
                self._next_medicine_id = max_id + 1

        if os.path.exists(sales_file):
            with open(sales_file, mode="r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                self._sales.clear()
                max_bill = 1000
                for row in reader:
                    bill_no = int(row["bill_no"])
                    cust_name = row["customer_name"]
                    cust_phone = row["customer_phone"]
                    timestamp = datetime.strptime(row["timestamp"], "%Y-%m-%d %H:%M:%S")
                    items = json.loads(row["items_json"])

                    customer = Customer(cust_name, cust_phone)
                    sale = Sale(bill_no, customer, items)
                    sale.timestamp = timestamp
                    self._sales.append(sale)
                    if bill_no > max_bill:
                        max_bill = bill_no
                self._next_bill_no = max_bill + 1


# ============================================================
#  INPUT HELPER FUNCTIONS (validation)
# ============================================================
def ask_nonempty(prompt):
    while True:
        value = input(prompt).strip()
        if value:
            return value
        print("  ! This field cannot be empty.")


def ask_int(prompt, minimum=None):
    while True:
        try:
            value = int(input(prompt).strip())
        except ValueError:
            print("  ! Please enter a whole number.")
            continue
        if minimum is not None and value < minimum:
            print(f"  ! Value must be at least {minimum}.")
            continue
        return value


def ask_float(prompt):
    while True:
        try:
            value = float(input(prompt).strip())
        except ValueError:
            print("  ! Please enter a number.")
            continue
        if value <= 0:
            print("  ! Value must be greater than zero.")
            continue
        return value


def ask_date(prompt):
    while True:
        try:
            return datetime.strptime(input(prompt).strip(), "%Y-%m-%d").date()
        except ValueError:
            print("  ! Use the format YYYY-MM-DD, for example 2027-06-30.")


def ask_yes_no(prompt):
    return input(prompt + " (y/n): ").strip().lower() == "y"


# ============================================================
#  CONSOLE APPLICATION CLASS
# ============================================================
class PharmacyApp:
    """Handles the menu and user interaction."""

    MENU = [
        ("1", "Add medicine"),
        ("2", "View all medicines"),
        ("3", "Search medicine"),
        ("4", "Restock medicine"),
        ("5", "Update price"),
        ("6", "Delete medicine"),
        ("7", "New bill (sell medicines)"),
        ("8", "Sales history & revenue"),
        ("9", "Alerts (low stock / expiry)"),
        ("10", "Export data to CSV"),
        ("11", "Import data from CSV"),
        ("0", "Exit"),
    ]

    def __init__(self, pharmacy):
        self.pharmacy = pharmacy

    def run(self):
        handlers = {
            "1": self.add_medicine,
            "2": self.view_medicines,
            "3": self.search_medicine,
            "4": self.restock_medicine,
            "5": self.update_price,
            "6": self.delete_medicine,
            "7": self.new_sale,
            "8": self.sales_history,
            "9": self.show_alerts,
            "10": self.export_csv,
            "11": self.import_csv,
        }
        print(f"\nWelcome to {self.pharmacy.name}!")
        while True:
            self.show_menu()
            choice = input("Enter your choice: ").strip()
            if choice == "0":
                print("Thank you for using the system. Goodbye!")
                break
            handler = handlers.get(choice)
            if handler is None:
                print("  ! Invalid choice, please try again.")
                continue
            try:
                handler()
            except PharmacyError as error:
                print(f"  ! {error}")
            except ValueError as error:
                print(f"  ! {error}")

    def show_menu(self):
        print("\n" + "=" * 46)
        print(f"  {self.pharmacy.name.upper()} - MAIN MENU")
        print("=" * 46)
        for key, label in self.MENU:
            print(f"  {key}. {label}")

    @staticmethod
    def _print_table(medicines, title=None):
        if title:
            print(f"\n{title}")
        if not medicines:
            print("  No medicines to show.")
            return
        print(TABLE_HEADER)
        print("-" * len(TABLE_HEADER))
        for medicine in medicines:
            print(medicine)

    # ---- menu actions ----
    def add_medicine(self):
        print("\n-- Add New Medicine --")
        name = ask_nonempty("Medicine name: ")
        price = ask_float("Price (Rs.): ")
        quantity = ask_int("Quantity in stock: ", minimum=0)
        expiry = ask_date("Expiry date (YYYY-MM-DD): ")
        prescription = ask_yes_no("Does it require a prescription?")
        medicine = self.pharmacy.add_medicine(name, price, quantity, expiry, prescription)
        print(f"  Medicine added successfully with ID {medicine.medicine_id}.")

    def view_medicines(self):
        self._print_table(self.pharmacy.all_medicines(), "-- All Medicines --")

    def search_medicine(self):
        keyword = ask_nonempty("Enter medicine name to search: ")
        self._print_table(self.pharmacy.search(keyword), f"-- Results for '{keyword}' --")

    def restock_medicine(self):
        medicine_id = ask_int("Medicine ID: ", minimum=1)
        medicine = self.pharmacy.get_medicine(medicine_id)
        amount = ask_int(f"Units to add to '{medicine.name}' "
                         f"(current stock {medicine.quantity}): ", minimum=1)
        self.pharmacy.restock(medicine_id, amount)
        print(f"  Stock updated. New quantity: {medicine.quantity}")

    def update_price(self):
        medicine_id = ask_int("Medicine ID: ", minimum=1)
        medicine = self.pharmacy.get_medicine(medicine_id)
        new_price = ask_float(f"New price for '{medicine.name}' (current "
                              f"Rs.{medicine.price:.2f}): ")
        medicine.update_price(new_price)
        print("  Price updated successfully.")

    def delete_medicine(self):
        medicine_id = ask_int("Medicine ID to delete: ", minimum=1)
        medicine = self.pharmacy.get_medicine(medicine_id)
        if ask_yes_no(f"Permanently delete '{medicine.name}'?"):
            self.pharmacy.delete_medicine(medicine_id)
            print("  Medicine deleted.")
        else:
            print("  Deletion cancelled.")

    def new_sale(self):
        print("\n-- New Bill --")
        customer = Customer(ask_nonempty("Customer name: "),
                            input("Customer phone (optional): ").strip())
        cart = []
        prescription_given = False

        while True:
            entry = input("Medicine ID to add ('done' to finish, 'x' to cancel): ").strip().lower()
            if entry == "x":
                print("  Bill cancelled.")
                return
            if entry == "done":
                break
            try:
                medicine_id = int(entry)
            except ValueError:
                print("  ! Please enter a valid medicine ID.")
                continue

            medicine = self.pharmacy.get_medicine(medicine_id)
            print(f"  {medicine.name} | Rs.{medicine.price:.2f} | In stock: {medicine.quantity}")

            if medicine.is_expired():
                print("  ! This medicine has expired and cannot be sold.")
                continue

            if medicine.requires_prescription and not prescription_given:
                prescription_given = ask_yes_no("  This needs a prescription. Is a valid one provided?")
                if not prescription_given:
                    print("  ! Item not added without a prescription.")
                    continue

            quantity = ask_int("  Quantity: ", minimum=1)
            cart.append((medicine_id, quantity))
            print("  Added to bill.")

        if not cart:
            print("  No items added. Bill not created.")
            return

        sale = self.pharmacy.create_sale(customer, cart, prescription_given)
        print("\n" + sale.receipt())

    def sales_history(self):
        sales = self.pharmacy.sales_history()
        if not sales:
            print("  No sales recorded yet.")
            return
        print("\n-- Sales History --")
        for sale in sales:
            print(f"  Bill #{sale.bill_no} | {sale.customer.name:<15} | "
                  f"{sale.timestamp:%d-%m-%Y %H:%M} | Rs.{sale.total:.2f}")
        print(f"\n  Total revenue so far: Rs.{self.pharmacy.total_revenue():.2f}")

    def show_alerts(self):
        self._print_table(self.pharmacy.low_stock_items(),
                          f"-- LOW STOCK (<= {LOW_STOCK_LIMIT} units) --")
        self._print_table(self.pharmacy.expiring_soon(30),
                          f"-- EXPIRING WITHIN 30 DAYS --")
        self._print_table(self.pharmacy.expired_items(), "-- EXPIRED --")

    def export_csv(self):
        print("\n-- Export to CSV --")
        try:
            self.pharmacy.export_to_csv("medicines.csv", "sales.csv")
            print("  Successfully exported data to 'medicines.csv' and 'sales.csv'.")
        except Exception as e:
            print(f"  ! Export failed: {e}")

    def import_csv(self):
        print("\n-- Import from CSV --")
        if ask_yes_no("Warning: Importing will overwrite current inventory and sales history. Continue?"):
            try:
                self.pharmacy.import_from_csv("medicines.csv", "sales.csv")
                print("  Successfully imported data from 'medicines.csv' and 'sales.csv'.")
            except Exception as e:
                print(f"  ! Import failed: {e}")
        else:
            print("  Import cancelled.")


# ============================================================
#  SAMPLE DATA & PROGRAM START
# ============================================================
def load_sample_data(pharmacy):
    today = date.today()
    pharmacy.add_medicine("Paracetamol 500mg", 25.00, 120, today + timedelta(days=400))
    pharmacy.add_medicine("Amoxicillin 250mg", 85.50, 8, today + timedelta(days=200), prescription=True)
    pharmacy.add_medicine("Cough Syrup 100ml", 60.00, 40, today + timedelta(days=15))
    pharmacy.add_medicine("Vitamin C Tablets", 150.00, 55, today + timedelta(days=300))
    pharmacy.add_medicine("Old Antacid", 12.00, 30, today - timedelta(days=10))


if __name__ == "__main__":
    pharmacy = Pharmacy("City Care Pharmacy")
    load_sample_data(pharmacy)
    PharmacyApp(pharmacy).run()