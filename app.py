import os

import click
import numpy as np
import pandas as pd
import spacy
import streamlit as st


def time_set():
    st.session_state["time_set"] = None


@click.command()
@click.option("--recipe_dir", help="Directory containing CookLang recipes.")
def main(recipe_dir):
    LANGUAGES = ["Englisch", "Deutsch"]
    lang_config = {
        "Deutsch": "de_core_news_sm",
        "Englisch": "en_core_web_sm",
    }
    UNITS = ["Stück", "Esslöffel (EL)", "Teelöffel (TL)", "Gramm (g)", "Milliliter (ml)", "Tassen (cup)", "Prise", "Dose"]
    TYPES = ["Zutat", "Utensil"]
    COURSE_TYPES = ["Frühstück", "Warme Mahlzeit", "Snack", "Kuchen"]


    text = """
    Die Kichererbsen waschen, abtropfen lassen und mit dem Stampfer leicht zerstampfen. Den Seitan würfeln. Kichererbsen und Seitan in 2 separaten Pfannen anbraten und zum Schluss die Gewürze unterrühren. Mit Salz und Pfeffer abschmecken.

    Die Tomaten würfeln, die eingelegten Paprika in Streifen schneiden, die Avocado halbieren und in Scheiben schneiden.

    Die Tortillas vor dem Belegen ohne Öl in einer Pfanne erwärmen. Spinat, Tomaten, Kichererbsen, Seitan, Paprika und Avocado auf den Tortillas verteilen. Die Tortillas aufrollen in etwas Folie wickeln, damit sie zusammenhalten. 
    """
    input_path = "/Users/philipp/Projekte/cooklang-recipe-writer/recipes/" if recipe_dir is None else recipe_dir
    recipe_path = st.sidebar.text_input("Dateipfad zum Rezeptordner:", value=input_path)
    language = st.sidebar.selectbox("Rezeptsprache:", LANGUAGES)
    separator = st.sidebar.selectbox("Trennzeichen für Schritte:", [".", ";", "\\n"], key="separator")
    if separator == "\\n":
        separator = "\n"
    course_type_input = st.sidebar.text_input("Mögliche Arten an Gängen:", value=", ".join(COURSE_TYPES))
    COURSE_TYPES = [x.strip() for x in course_type_input.split(",")]

    st.header("Original Rezept")
    input = st.text_area("Rezept:", value=text, height=300, key="recipe_input")

    input = input.strip()

    nlp = spacy.load(lang_config[language])
    doc = nlp(input)
    nouns = sorted(set([str(word).strip() for word in doc if word.pos_ in ["NOUN", "PROPN"]]))

    st.header("Semantische Informationen hinterlegen")
    st.subheader("Meta-Daten")
    name = st.text_input("Name:")
    left, mid, right = st.columns([2, 1, 1])
    image = st.file_uploader("Rezeptbild:", ["png", "jpg"], accept_multiple_files=False)
    if image:
        image_suffix = image.name.split(".")[-1:][0]
    source = left.text_input("Quelle (Webseite):")
    time = mid.number_input("Zubereitungszeit (min):", value=30, on_change=time_set)
    course = right.selectbox("Gang:", COURSE_TYPES)

    st.subheader("Zutaten und Utensilien")
    to_remove = st.multiselect("Keine Zutat oder kein Utensil:", nouns)

    nouns = [word for word in nouns if word not in to_remove]
    n_words = len(nouns)

    data = pd.DataFrame(data={
        "Begriff": nouns,
        "Eintragsart": np.full((n_words), "Zutat"),
        "Menge": np.full((n_words), None),
        "Einheit": np.full((n_words), None)
        })
    user_data = st.data_editor(data, column_config={
        "Eintragsart": st.column_config.SelectboxColumn(
            options=TYPES,
        ),
        "Menge": st.column_config.NumberColumn(),
        "Einheit": st.column_config.SelectboxColumn(
            options=UNITS
        )},
        num_rows="dynamic",
        use_container_width=True
        )


    st.header("CookLang Vorschau")

    output = ""
    # Meta-Data
    if source is not None and len(source) > 1:
        output += f">> source: {source}\n"
    if "time_set" in st.session_state:
        output += f">> time: {time} min\n"
    if course is not None and len(course) > 1:
        output += f">> course: {course}\n\n"

    output += input.replace(separator+" ", ".\n\n")

    # Aufteilung in Eintragsarten
    user_data = user_data.set_index("Begriff")
    ingredients = [word for word in user_data.index.values if user_data.loc[word, "Eintragsart"] == "Zutat"]
    utensils = [word for word in user_data.index.values if user_data.loc[word, "Eintragsart"] == "Utensil"]

    # CookLang-Syntax-Umwandlung
    for word in ingredients:
        old = word
        amount = user_data.loc[word, "Menge"]
        unit = user_data.loc[word, "Einheit"]
        type_ = user_data.loc[word, "Eintragsart"]

        if amount is None or unit is None:
            new = "@"+old
            if " " in old:
                new += "{}"
        else:
            if str(amount)[-2:] == ".0":
                amount = int(amount)
            if "(" in unit:
                start = unit.find("(") + 1
                stop = unit.find(")")
                unit = unit[start:stop]
            new = "@" + old + "{" + str(amount) + "%" + unit + "}"
        output = output.replace(old, new, 1)
    for word in utensils:
        old = word
        new = "#" + old
        if " " in old:
            new += "{}"
        output = output.replace(old, new, 1)


    output = st.text_area("Ausgabe:", value=output, height=400, key="output")

    # Download-Optionen
    left, mid_left, mid_right, right = st.columns([1, 1, 1, 2])
    if left.button("Rezept speichern"):
        try:
            with open(os.path.join(recipe_path, f"{name}.cook"), "w") as f:
                f.write(output)
            with open(os.path.join(recipe_path, f"{name}.{image_suffix}"), "wb") as f:
                f.write(image.getbuffer())
            st.success("Rezept wurde gespeichert.")
        except Exception as ex:
            st.error(ex)
    if name is not None and len(name) > 1:
        mid_left.download_button("Rezept runterladen", output, f"{name}.cook")
        if image:
            mid_right.download_button("Rezeptbild runterladen", image, f"{name}.{image_suffix}")


if __name__ == "__main__":
    main()