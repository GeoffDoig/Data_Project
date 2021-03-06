import os
import env
import json
from flask import Flask, render_template, redirect, request, url_for, session, flash
from flask_paginate import Pagination, get_page_args
from flask_pymongo import PyMongo
from bson.objectid import ObjectId

app = Flask(__name__)
app.secret_key = os.getenv("SECRET", "secret123string")
app.config["MONGO_URI"] = os.getenv("MONGO_URI")
app.config["MONGO_DBNAME"] = os.getenv("MONGO_DBNAME")

mongo = PyMongo(app)

options = {}

def selection():
    """Populate options with chosen fields"""
    if request.form.get("style_name"):
        option = {"style_name": request.form.get("style_name")}
        options.update(option)
    if request.form.get("author_name"): 
        option = {"author_name": request.form.get("author_name")}
        options.update(option)
    if request.form.get("ingredient_name"): 
        option = {"ingredients.ingredient_name": request.form.get("ingredient_name")}
        options.update(option)
    if request.form.get("allergen_name"): 
        option = {"allergen_name": request.form.get("allergen_name")}
        options.update(option)
    
@app.route('/', methods = ["GET", "POST"])
def index():
    """Welcome / Sign in page"""
    if request.method == "POST":
        session["username"] = request.form["username"]
    if "username" in session:
        return redirect(url_for("search", username = session["username"]))
    return render_template("index.html")
    
@app.route('/search')
def search():
    """Display search options to the user"""
    options.clear()
    styles = mongo.db.categories.find_one({"category_name": "cuisine"})
    chefs = mongo.db.categories.find_one({"category_name": "authors"})
    items = mongo.db.categories.find_one({"category_name": "ingredients"})
    alls = mongo.db.categories.find_one({"category_name": "allergens"})
    return render_template("search.html", cuisine = styles, authors = chefs, ingredients = items, allergens = alls)
    
@app.route('/results', methods = ["GET", "POST"])
def results():
    """Display results of search with or without options and apply pagination to page"""
    selection()
    page = int(request.args.get("page", 1))
    per_page = 5
    offset = (page - 1) * per_page
    if options:
        choices = mongo.db.recipes.find(options).sort("views", -1).limit(per_page).skip(offset)
    else:
        choices = mongo.db.recipes.find().sort("views", -1).limit(per_page).skip(offset)
    pagination = Pagination(page = page, per_page = per_page, offset = offset, total = choices.count(), record_name = "recipes")
    return render_template("results.html", choices = choices, pagination = pagination)

@app.route('/add_recipe')
def add_recipe():
    """Display form to add a recipe to database"""
    return render_template("addrecipe.html")
    
@app.route('/insert_recipe', methods = ["POST"])
def insert_recipe():
    """Check database to see if search categories exist and add them to database if not"""
    styles = mongo.db.categories.find_one({"category_name": "cuisine"})
    if request.form["style_name"] not in styles:
        new_style = request.form["style_name"].lower()
        mongo.db.categories.update({"category_name": "cuisine"}, 
            {"$addToSet": {"style": {"style_name": new_style}}})
    chefs = mongo.db.categories.find_one({"category_name": "authors"})
    if request.form["author_name"] not in chefs:
        new_author = request.form["author_name"].lower()
        mongo.db.categories.update({"category_name": "authors"},
            {"$addToSet": {"author": {"author_name": new_author}}})
    #Create and populate list of ingredients and add any new ingredients to database category
    ingredientsList = []
    ingredientItems = request.form.getlist("ingredient_name")
    ingredientQty = request.form.getlist("quantity")
    items = mongo.db.categories.find_one({"category_name": "ingredients"})
    i = 0
    while i < len(ingredientItems):
        if not ingredientItems[i]:
            break
        elif ingredientItems[i] not in items:
            mongo.db.categories.update({"category_name": "ingredients"},
                {"$addToSet": {"ingredient": {"ingredient_name": ingredientItems[i].lower()}}})
        ingredient = {"ingredient_name": ingredientItems[i].lower(), "quantity": ingredientQty[i]}
        ingredientsList.append(ingredient)
        i +=1
    #Evaluate allergens entered and add any new allergens to database category
    if request.form.get("allergens") == "on":
        allergens = True
        allergen_name = request.form["allergen_name"].lower()
        alls = mongo.db.categories.find_one({"category_name": "allergens"})
        if request.form["allergen_name"] not in alls:
            new_allergen = allergen_name
            mongo.db.categories.update({"category_name": "allergens"},
                {"$addToSet": {"allergen": {"allergen_name": new_allergen}}})
    else:
        allergens = False
        allergen_name = ""
    #Create and populate new recipe document and add to database
    new_recipe = {
        "recipe_name": request.form["recipe_name"].lower(),
        "style_name": request.form["style_name"].lower(),
        "author_name": request.form["author_name"].lower(),
        "ingredients": ingredientsList,
        "instructions": json.dumps(request.form["instructions"]),
        "allergens": allergens,
        "allergen_name": allergen_name,
        "views": 0
    }
    mongo.db.recipes.insert_one(new_recipe)
    flash("You have successfully added your recipe")
    return redirect(url_for("search"))
      
@app.route('/recipe/<choice_id>', methods = ["GET", "POST"])
def recipe(choice_id):
    """Display an individual recipe"""
    the_recipe = mongo.db.recipes.find_one({"_id": ObjectId(choice_id)})
    the_instructions = json.loads(the_recipe["instructions"])
    new_view = the_recipe.get("views")
    new_view +=1
    mongo.db.recipes.update_one(the_recipe, {"$set": {"views": new_view}})
    return render_template("recipe.html", recipe = the_recipe, instruction = the_instructions)

@app.route('/edit_recipe/<recipe_id>', methods = ["GET", "POST"])
def edit_recipe(recipe_id):
    """Display form to edit a specifically chosen recipe"""
    the_recipe = mongo.db.recipes.find_one({"_id": ObjectId(recipe_id)})
    the_instructions = json.loads(the_recipe["instructions"])
    return render_template("editrecipe.html", recipe = the_recipe, instruction = the_instructions)
    
@app.route('/update_recipe/<recipe_id>', methods = ["POST"])
def update_recipe(recipe_id):
    """Create new list of ingredients with any changes"""
    ingredientsList = []
    ingredientItems = request.form.getlist("ingredient_name")
    ingredientQty = request.form.getlist("quantity")
    i = 0
    while i < len(ingredientItems):
        if not ingredientItems[i]:
            break
        ingredient = {"ingredient_name": ingredientItems[i].lower(), "quantity": ingredientQty[i]}
        ingredientsList.append(ingredient)
        i +=1
    #Evaluate any allergen information added
    if request.form.get("allergens") == "on":
        allergens = True
        allergen_name = request.form["allergen_name"].lower()
    else:
        allergens = False
        allergen_name = ""
    #Update specific recipe on database with information provided
    mongo.db.recipes.update({"_id": ObjectId(recipe_id)},
        {
            "recipe_name": request.form["recipe_name"].lower(),
            "style_name": request.form["style_name"].lower(),
            "author_name": request.form["author_name"].lower(),
            "ingredients": ingredientsList,
            "instructions": json.dumps(request.form["instructions"]),
            "allergens": allergens,
            "allergen_name": allergen_name,
            "views": int(request.form.get("views"))
        })
    flash("You have successfully changed your recipe")
    return redirect(url_for("results"))

@app.route('/delete_recipe/<recipe_id>')
def delete_recipe(recipe_id):
    """Remove selected recipe from database"""
    mongo.db.recipes.remove({"_id": ObjectId(recipe_id)})
    flash("You have successfully removed your recipe")
    return redirect(url_for("search"))

@app.route('/logout')
def logout():
    """Log user out of CookBook and return to sign in page"""
    session.pop("username", None)
    return redirect(url_for("index"))

if __name__ == '__main__':
    app.run(host = os.getenv('IP', '0.0.0.0'), port = int(os.getenv('PORT', '5000')), debug = False)
    