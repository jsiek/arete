

for parameters, local variables, pattern variables
need to say 
* how much priviledge: read, write
* how long: temporary, forever

alternative: what does return mean for pointers?
Do we need an annotation on functions to declare read/write or share/take?

Does return create a copy of the pointer?
If so, when is the copy killed?
Should interp_exp also return a boolean that says whether the result
is a temporary object. And the caller can kill the result after it is used?
Or should we pass the destination to interp_exp?

Or should interp_exp always create a copy, a temporary, and
the caller should always kill the result after using it?

some expressions create a temporary pointer:
* new 10
other expressions don't
* y

How to handle difference between

	{
	  var x = take new 10;
	}

which should not copy the pointer, 
and delete the pointer when x goes out of scope

versus

	{
	  var y = take new 10;
	  {
		var x = share y;
	  }
	  y := 0;
	  return y;
	}

which should copy the pointer, changing y to read only,
and then changing y back to write when x goes out of
scope.




# Related Literature


* Dala: A Simple Capability-Based Dynamic Language Design for Data Race-Freedom
  Fernandez-Reyes, Kiko and Gariano, Isaac Oscar and Noble, James
  and Greenwood-Thessman, Erin and Homer, Michael and Wrigstad, Tobias
  Onward! 2021
  Fernandez-Reyes:2021uy

  categories:
    * IMMutable and shared
	* mutable and ISOlated
	* thread LOCAL
	* unsafe
  a category is fixed for each object at creatoin
  hierarchy: imm < iso < local < unsafe.
  
    Objects can only refer to other objects with the same or lesser
    capabilities: an immutable object can only refer to other
    immutable objects; an isolate object can refer to other isos or
    imms, and a local object can refer to imms, isos, and other local
    objects.

  prove:
  * data race freedom
  * gradual guarantee 
  
  implemented in the Grace language

* Dynamic Ownership in a Dynamic Language
  Gordon, Donald and Noble, James
  DLS 2007
  Gordon:2007vq
  
  Maintain an ownership tree: each object has a pointer to its owner.
  Check message sends to make sure that the receiver is visible to
  the sender.

* Object ownership for dynamic alias protection. 
  James Noble, David Clarke, and John Potter. 
  TOOLS 1999
  Noble:1999um
  
  precursor to "Dynamic Ownership in a Dynamic Language"

* Robust Composition ("E" language)
  Mark Miller
  Ph.D. Thesis 2006, Johns Hopkins Univ.

  Deep copy
  Far references
 
* Newspeak

  Deep copy
  Far references
  
* AmbientTalk

  Deep copy
  Far references
  
* Erlang

  Deep copy

* Gradual typestate
  Wolff, Roger and Garcia, Ronald and Tanter, \'{E}ric and Aldrich, Jonathan
  ECOOP 2011
  Wolff:2011hc

* Gradual Ownership Types
  I. Sergey, D. Clarke In ESOP 2012, LNCS, vol. 7211, pp. 579–599, 2012.
  
