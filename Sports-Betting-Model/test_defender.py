import streamlit as st

st.title("Defender Test")
defender = st.text_input("Enter defender name")
st.write(f"Defender entered: {defender}")