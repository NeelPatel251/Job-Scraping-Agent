from bs4 import BeautifulSoup

async def resolve_radio_input_id(self, fieldset_id: str, value: str) -> str:
    """
    Find the actual <input> ID for a given value (e.g., 'Yes') inside a radio fieldset.
    It looks for data-test-text-selectable-option__input="value" in inputs within the fieldset.
    """
    try:
        html = await self.page.content()
        soup = BeautifulSoup(html, "html.parser")

        # Find the fieldset element
        fieldset = soup.find("fieldset", {"id": fieldset_id})
        if not fieldset:
            print(f"[resolve_radio_input_id] Fieldset not found: {fieldset_id}")
            return fieldset_id  # fallback to original

        # Loop through all input elements and match by value
        input_elems = fieldset.find_all("input")
        for inp in input_elems:
            if (
                inp.get("data-test-text-selectable-option__input", "").strip().lower() == value.strip().lower()
                and inp.has_attr("id")
            ):
                print(f"[resolve_radio_input_id] Matched input ID: {inp['id']} for value: {value}")
                return inp["id"]

        print(f"[resolve_radio_input_id] No matching input found in fieldset for value: {value}")
        return fieldset_id  # fallback
    except Exception as e:
        print(f"[resolve_radio_input_id] Error: {e}")
        return fieldset_id
