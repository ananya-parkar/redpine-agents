# agent-3/dashboard/test_dashboard_local.py

from dashboard.dashboard import generate_dashboard

if __name__ == "__main__":
    output_path = "test_dashboard_output.xlsx"
    generate_dashboard(output_path)
    print(f"\nOpen {output_path} to review formatting changes.")