def route(page: str):
    if page == "main":
        from ui.pages.dashboard import page_main
        page_main()
    elif page == "register":
        from ui.pages.register import page_register
        page_register()
    elif page == "clients":
        from ui.pages.clients import page_clients
        page_clients()
    elif page == "order_registration":
        from ui.pages.purchase import page_purchase_order
        page_purchase_order()
    elif page == "order_confirmation":
        from ui.pages.order_confirmation import page_order_confirmation
        page_order_confirmation()
    elif page == "delivery_confirmation":
        from ui.pages.delivery import page_delivery_confirmation
        page_delivery_confirmation()
    elif page == "reservation":
        from ui.pages.reservation import page_reservation
        page_reservation()
    elif page == "sale_validation":
        from ui.pages.placeholders import page_placeholder
        page_placeholder("Validar Venta", "sale_validation")
    elif page == "employee_registration":
        from ui.pages.placeholders import page_placeholder
        page_placeholder("Registrar Empleado", "employee_registration")
