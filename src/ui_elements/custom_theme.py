import streamlit as st

hide_menu_style = """
<style>
#MainMenu {visibility: hidden;}
</style>
"""

def set_custom_theme():
    st.markdown(hide_menu_style, unsafe_allow_html=True) 