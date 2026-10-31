<style>
    /* Ocultar menú */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    
    /* Hacer el encabezado transparente para que la flechita se vea, pero sin fondo blanco */
    header { background: transparent !important; }

    /* Fondo con degradado espacial */
    .stApp {
        background: linear-gradient(135deg, #0f0c29, #302b63, #24243e);
        color: #e0e0e0;
    }

    /* Barra lateral con efecto cristal */
    [data-testid="stSidebar"] {
        background: rgba(15, 12, 41, 0.7);
        backdrop-filter: blur(12px);
        border-right: 1px solid rgba(255, 255, 255, 0.1);
    }

    /* Burbujas de chat estilo cristal */
    .stChatMessage {
        background: rgba(255, 255, 255, 0.05);
        backdrop-filter: blur(10px);
        border: 1px solid rgba(255, 255, 255, 0.1);
        border-radius: 20px;
        padding: 1.2rem;
        margin-bottom: 1.5rem;
        box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.3);
        color: #ffffff;
    }

    /* Botones elegantes */
    .stButton>button {
        background: linear-gradient(90deg, #4b33a8 0%, #1d4ed8 100%);
        color: white;
        border: none;
        border-radius: 10px;
        transition: transform 0.2s;
    }
    .stButton>button:hover {
        transform: scale(1.05);
    }
</style>
